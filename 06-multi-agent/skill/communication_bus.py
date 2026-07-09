"""
Agent 通信总线

实现多种通信方式：
1. 集中式通信（CentralizedBus）：所有消息通过调度员中转
2. 点对点通信（DirectBus）：Agent之间直接通信
3. 发布-订阅（PubSubBus）：Agent发布消息到主题，订阅者接收
4. 共享黑板（BlackboardBus）：所有Agent访问共享状态空间

关键设计：
- 消息序列化：只传递可序列化的数据
- 全局追踪：所有消息带 Trace ID
- 消息优先级：支持紧急消息优先处理
- 消息过滤：避免消息风暴
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from queue import PriorityQueue
from threading import Lock
from .agent_swarm import Message

logger = logging.getLogger(__name__)


@dataclass
class PrioritizedMessage:
    """带优先级的消息"""
    priority: int  # 数字越小优先级越高
    message: Message

    def __lt__(self, other):
        return self.priority < other.priority


class CentralizedBus:
    """
    集中式通信总线
    
    所有消息通过中心节点中转，便于监控和仲裁。
    
    适用场景：
    - 主子模式（Hierarchical）
    - 需要全局监控的协作
    - 消息需要仲裁的情况
    
    优点：易于监控、便于仲裁、通信可控
    缺点：调度员压力大、延迟增加
    """

    def __init__(self, max_queue_size: int = 1000):
        self.message_queue: List[Message] = []
        self.max_queue_size = max_queue_size
        self.coordinator: Optional[str] = None
        self._lock = Lock()

    def set_coordinator(self, name: str) -> None:
        """设置中心调度员"""
        self.coordinator = name
        logger.info(f"[CentralizedBus] 设置调度员: {name}")

    def send(self, message: Message) -> bool:
        """发送消息到总线"""
        with self._lock:
            if len(self.message_queue) >= self.max_queue_size:
                logger.warning(f"[CentralizedBus] 消息队列已满，丢弃消息: {message.id}")
                return False

            self.message_queue.append(message)
            logger.info(f"[CentralizedBus] 消息入队: {message.sender} -> {message.receiver}")
            return True

    def receive(self, receiver: str) -> List[Message]:
        """接收指定Agent的消息"""
        with self._lock:
            messages = [
                msg for msg in self.message_queue
                if msg.receiver == receiver or msg.receiver == "all"
            ]
            # 移除已接收的消息
            self.message_queue = [
                msg for msg in self.message_queue
                if msg not in messages
            ]
            return messages

    def broadcast(self, sender: str, content: Any, trace_id: str = "") -> None:
        """广播消息给所有Agent"""
        message = Message(
            trace_id=trace_id,
            sender=sender,
            receiver="all",
            content=content,
            message_type="broadcast"
        )
        self.send(message)

    def get_stats(self) -> Dict[str, Any]:
        """获取总线统计信息"""
        return {
            "queue_size": len(self.message_queue),
            "max_size": self.max_queue_size,
            "coordinator": self.coordinator
        }


class DirectBus:
    """
    点对点通信总线
    
    Agent之间直接发送消息，不经过中心节点。
    
    适用场景：
    - 平等协作（Round Robin）
    - 需要低延迟的通信
    - Agent数量较少的情况
    
    优点：延迟低、效率高
    缺点：难以监控、可能消息风暴
    """

    def __init__(self):
        self.agent_queues: Dict[str, List[Message]] = {}
        self.message_log: List[Message] = []  # 用于事后追踪
        self._lock = Lock()

    def register_agent(self, name: str) -> None:
        """注册Agent的消息队列"""
        with self._lock:
            if name not in self.agent_queues:
                self.agent_queues[name] = []
                logger.info(f"[DirectBus] 注册Agent队列: {name}")

    def send_direct(self, sender: str, receiver: str, content: Any, trace_id: str = "") -> bool:
        """直接发送消息"""
        message = Message(
            trace_id=trace_id,
            sender=sender,
            receiver=receiver,
            content=content,
            message_type="direct"
        )

        with self._lock:
            if receiver not in self.agent_queues:
                logger.warning(f"[DirectBus] 接收者未注册: {receiver}")
                return False

            self.agent_queues[receiver].append(message)
            self.message_log.append(message)
            logger.info(f"[DirectBus] 直接消息: {sender} -> {receiver}")
            return True

    def receive(self, receiver: str) -> List[Message]:
        """接收消息"""
        with self._lock:
            if receiver not in self.agent_queues:
                return []
            messages = self.agent_queues[receiver].copy()
            self.agent_queues[receiver] = []
            return messages

    def get_communication_graph(self) -> Dict[str, Set[str]]:
        """获取通信关系图"""
        graph: Dict[str, Set[str]] = {}
        for msg in self.message_log:
            if msg.sender not in graph:
                graph[msg.sender] = set()
            graph[msg.sender].add(msg.receiver)
        return graph


class PubSubBus:
    """
    发布-订阅通信总线
    
    Agent发布消息到主题，订阅该主题的Agent会收到消息。
    
    适用场景：
    - Agent平台模式（动态发现）
    - 需要灵活订阅的场景
    - 广播通知
    
    优点：灵活、支持广播
    缺点：消息可能泛滥、需要过滤机制
    """

    def __init__(self):
        self.topics: Dict[str, List[Message]] = {}  # topic -> messages
        self.subscriptions: Dict[str, Set[str]] = {}  # topic -> subscribers
        self.agent_topics: Dict[str, Set[str]] = {}  # agent -> subscribed topics
        self._lock = Lock()

    def create_topic(self, topic: str) -> None:
        """创建主题"""
        with self._lock:
            if topic not in self.topics:
                self.topics[topic] = []
                self.subscriptions[topic] = set()
                logger.info(f"[PubSubBus] 创建主题: {topic}")

    def subscribe(self, agent: str, topic: str) -> None:
        """订阅主题"""
        with self._lock:
            if topic not in self.subscriptions:
                self.subscriptions[topic] = set()
            self.subscriptions[topic].add(agent)

            if agent not in self.agent_topics:
                self.agent_topics[agent] = set()
            self.agent_topics[agent].add(topic)

            logger.info(f"[PubSubBus] {agent} 订阅主题: {topic}")

    def unsubscribe(self, agent: str, topic: str) -> None:
        """取消订阅"""
        with self._lock:
            if topic in self.subscriptions:
                self.subscriptions[topic].discard(agent)
            if agent in self.agent_topics:
                self.agent_topics[agent].discard(topic)

    def publish(self, sender: str, topic: str, content: Any, trace_id: str = "") -> int:
        """发布消息到主题"""
        message = Message(
            trace_id=trace_id,
            sender=sender,
            receiver=topic,
            content=content,
            message_type="pubsub",
            metadata={"topic": topic}
        )

        with self._lock:
            if topic not in self.topics:
                self.topics[topic] = []
            self.topics[topic].append(message)

            # 返回订阅者数量
            subscriber_count = len(self.subscriptions.get(topic, set()))
            logger.info(f"[PubSubBus] 发布到主题 {topic}, {subscriber_count} 个订阅者")
            return subscriber_count

    def receive(self, agent: str) -> Dict[str, List[Message]]:
        """接收订阅的消息"""
        with self._lock:
            result = {}
            subscribed_topics = self.agent_topics.get(agent, set())

            for topic in subscribed_topics:
                messages = self.topics.get(topic, [])
                result[topic] = messages.copy()
                # 清空已消费的消息
                self.topics[topic] = []

            return result

    def list_topics(self) -> List[str]:
        """列出所有主题"""
        return list(self.topics.keys())


class BlackboardBus:
    """
    共享黑板通信
    
    所有Agent访问共享状态空间，可以读取和写入。
    
    适用场景：
    - 团队流水线（Team Pipeline）
    - 需要增量协作的场景
    - 数据共享
    
    优点：易于共享信息、支持增量式工作
    缺点：需要锁机制、可能有数据竞争
    """

    def __init__(self):
        self.state: Dict[str, Any] = {}
        self.state_history: List[Dict[str, Any]] = []
        self.locks: Dict[str, Lock] = {}
        self._global_lock = Lock()
        self.max_history = 100

    def write(self, key: str, value: Any, agent: str, trace_id: str = "") -> bool:
        """写入状态"""
        with self._global_lock:
            if key not in self.locks:
                self.locks[key] = Lock()

        with self.locks[key]:
            # 记录历史
            old_value = self.state.get(key)
            self.state[key] = value

            if len(self.state_history) >= self.max_history:
                self.state_history.pop(0)
            self.state_history.append({
                "timestamp": time.time(),
                "key": key,
                "agent": agent,
                "trace_id": trace_id,
                "old_value": old_value,
                "new_value": value
            })

            logger.info(f"[Blackboard] {agent} 写入 {key}")
            return True

    def read(self, key: str, agent: str) -> Optional[Any]:
        """读取状态"""
        with self._global_lock:
            if key not in self.locks:
                self.locks[key] = Lock()

        with self.locks[key]:
            value = self.state.get(key)
            logger.info(f"[Blackboard] {agent} 读取 {key}")
            return value

    def read_all(self, agent: str) -> Dict[str, Any]:
        """读取所有状态"""
        with self._global_lock:
            logger.info(f"[Blackboard] {agent} 读取全部状态")
            return self.state.copy()

    def get_history(self, key: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取状态变更历史"""
        if key:
            return [h for h in self.state_history if h["key"] == key]
        return self.state_history.copy()

    def clear(self, keys: Optional[List[str]] = None) -> None:
        """清空状态"""
        with self._global_lock:
            if keys:
                for key in keys:
                    self.state.pop(key, None)
            else:
                self.state.clear()
            logger.info(f"[Blackboard] 状态清空")


def create_bus(mode: str) -> Any:
    """根据模式创建通信总线"""
    if mode == "centralized":
        return CentralizedBus()
    elif mode == "direct":
        return DirectBus()
    elif mode == "pubsub":
        return PubSubBus()
    elif mode == "blackboard":
        return BlackboardBus()
    else:
        raise ValueError(f"未支持的通信模式: {mode}")