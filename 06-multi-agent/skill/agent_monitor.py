"""
Agent 容错监控模块

企业级多 Agent 系统必须处理以下问题：
1. Agent 死机/失联：如何检测？如何处理？
2. 调用超时：如何重试？如何降级？
3. 连续失败：如何熔断？如何恢复？
4. 负载不均：如何均衡？如何限流？

实现机制：
- 心跳检测：定期检查 Agent 健康状态
- 超时重试：调用超时时自动重试
- 故障转移：主 Agent 失败时切换到备用
- 熔断机制：连续失败时快速失败
- 服务降级：资源不足时降低服务质量
"""
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent 健康状态"""
    HEALTHY = "healthy"           # 健康
    UNRESPONSIVE = "unresponsive" # 无响应（心跳超时）
    FAILED = "failed"             # 失败（调用异常）
    CIRCUIT_OPEN = "circuit_open" # 熔断中
    DEGRADED = "degraded"         # 降级服务


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常（关闭）
    OPEN = "open"           # 熔断（打开）
    HALF_OPEN = "half_open" # 半开（试探）


@dataclass
class AgentHealth:
    """Agent 健康记录"""
    agent_name: str
    status: AgentStatus = AgentStatus.HEALTHY
    last_heartbeat: float = 0.0
    last_call_time: float = 0.0
    total_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    avg_response_time_ms: float = 0.0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_opened_at: float = 0.0
    failover_target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "consecutive_failures": self.consecutive_failures,
            "circuit_state": self.circuit_state.value,
            "avg_response_time_ms": round(self.avg_response_time_ms, 2)
        }


class HeartbeatMonitor:
    """
    心跳监控器

    定期检查 Agent 是否存活：
    1. 每个 Agent 需要定期发送心跳
    2. 超过 timeout 未收到心跳，标记为 UNRESPONSIVE
    3. 连续多次无响应，标记为 FAILED
    """

    def __init__(self, heartbeat_timeout: float = 10.0, check_interval: float = 5.0):
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval
        self.agents: Dict[str, AgentHealth] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def register(self, agent_name: str) -> None:
        """注册 Agent 到监控器"""
        with self._lock:
            self.agents[agent_name] = AgentHealth(agent_name=agent_name)
            logger.info(f"[HeartbeatMonitor] 注册 Agent: {agent_name}")

    def heartbeat(self, agent_name: str) -> None:
        """Agent 发送心跳"""
        with self._lock:
            if agent_name in self.agents:
                health = self.agents[agent_name]
                health.last_heartbeat = time.time()
                if health.status in [AgentStatus.UNRESPONSIVE, AgentStatus.FAILED]:
                    health.status = AgentStatus.HEALTHY
                    logger.info(f"[HeartbeatMonitor] Agent {agent_name} 恢复心跳")

    def get_health(self, agent_name: str) -> Optional[AgentHealth]:
        """获取 Agent 健康状态"""
        with self._lock:
            return self.agents.get(agent_name)

    def get_all_health(self) -> Dict[str, AgentHealth]:
        """获取所有 Agent 健康状态"""
        with self._lock:
            return self.agents.copy()

    def start(self) -> None:
        """启动心跳检查线程"""
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("[HeartbeatMonitor] 心跳检查已启动")

    def stop(self) -> None:
        """停止心跳检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("[HeartbeatMonitor] 心跳检查已停止")

    def _check_loop(self) -> None:
        """心跳检查循环"""
        while self._running:
            self._check_all_agents()
            time.sleep(self.check_interval)

    def _check_all_agents(self) -> None:
        """检查所有 Agent"""
        now = time.time()
        with self._lock:
            for name, health in self.agents.items():
                if health.status == AgentStatus.CIRCUIT_OPEN:
                    continue  # 熔断状态的 Agent 不检查心跳

                elapsed = now - health.last_heartbeat
                if elapsed > self.heartbeat_timeout:
                    if health.status == AgentStatus.HEALTHY:
                        health.status = AgentStatus.UNRESPONSIVE
                        logger.warning(f"[HeartbeatMonitor] Agent {name} 心跳超时 ({elapsed:.1f}s)")
                    elif health.status == AgentStatus.UNRESPONSIVE and elapsed > self.heartbeat_timeout * 2:
                        health.status = AgentStatus.FAILED
                        logger.error(f"[HeartbeatMonitor] Agent {name} 判定为失败")


class RetryPolicy:
    """
    重试策略

    支持多种重试策略：
    - 固定间隔：每次等待固定时间
    - 指数退避：等待时间指数增长
    - 随机抖动：避免惊群效应
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 30.0, exponential: bool = True,
                 jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """获取第 attempt 次重试的等待时间"""
        import random

        if self.exponential:
            delay = self.base_delay * (2 ** attempt)
        else:
            delay = self.base_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    def execute(self, func: Callable, *args, **kwargs) -> Tuple[bool, Any, int]:
        """
        执行函数，失败时自动重试

        Returns:
            (success, result, attempts)
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                return True, result, attempt + 1
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(f"[RetryPolicy] 第 {attempt + 1} 次失败，{delay:.1f}s 后重试: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"[RetryPolicy] 重试耗尽 ({self.max_retries} 次): {e}")

        return False, last_exception, self.max_retries + 1


class CircuitBreaker:
    """
    熔断器

    防止故障扩散：
    1. CLOSED：正常状态，允许调用
    2. OPEN：熔断状态，快速失败
    3. HALF_OPEN：半开状态，允许试探调用

    触发条件：
    - 连续失败次数达到阈值 → 熔断（OPEN）
    - 熔断后等待一段时间 → 半开（HALF_OPEN）
    - 半开状态下成功 → 关闭（CLOSED）
    - 半开状态下失败 → 重新熔断（OPEN）
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.states: Dict[str, CircuitState] = {}
        self.failure_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}
        self.half_open_calls: Dict[str, int] = {}
        self._lock = threading.Lock()

    def get_state(self, agent_name: str) -> CircuitState:
        """获取熔断器状态"""
        with self._lock:
            state = self.states.get(agent_name, CircuitState.CLOSED)

            # 检查是否需要从 OPEN 转为 HALF_OPEN
            if state == CircuitState.OPEN:
                opened_time = self.opened_at.get(agent_name, 0)
                if time.time() - opened_time > self.recovery_timeout:
                    self.states[agent_name] = CircuitState.HALF_OPEN
                    self.half_open_calls[agent_name] = 0
                    self.success_counts[agent_name] = 0
                    logger.info(f"[CircuitBreaker] Agent {agent_name} 进入半开状态")
                    return CircuitState.HALF_OPEN

            return state

    def record_success(self, agent_name: str) -> None:
        """记录成功调用"""
        with self._lock:
            state = self.states.get(agent_name, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                self.success_counts[agent_name] = self.success_counts.get(agent_name, 0) + 1
                self.half_open_calls[agent_name] = self.half_open_calls.get(agent_name, 0) + 1

                # 半开状态下连续成功，关闭熔断器
                if self.success_counts[agent_name] >= self.half_open_max_calls:
                    self.states[agent_name] = CircuitState.CLOSED
                    self.failure_counts[agent_name] = 0
                    logger.info(f"[CircuitBreaker] Agent {agent_name} 熔断器关闭（恢复）")

            elif state == CircuitState.CLOSED:
                self.failure_counts[agent_name] = 0

    def record_failure(self, agent_name: str) -> None:
        """记录失败调用"""
        with self._lock:
            state = self.states.get(agent_name, CircuitState.CLOSED)

            if state == CircuitState.HALF_OPEN:
                # 半开状态下失败，重新熔断
                self.states[agent_name] = CircuitState.OPEN
                self.opened_at[agent_name] = time.time()
                logger.warning(f"[CircuitBreaker] Agent {agent_name} 半开状态失败，重新熔断")

            elif state == CircuitState.CLOSED:
                self.failure_counts[agent_name] = self.failure_counts.get(agent_name, 0) + 1

                # 连续失败达到阈值，熔断
                if self.failure_counts[agent_name] >= self.failure_threshold:
                    self.states[agent_name] = CircuitState.OPEN
                    self.opened_at[agent_name] = time.time()
                    logger.error(f"[CircuitBreaker] Agent {agent_name} 熔断器打开（连续失败 {self.failure_threshold} 次）")

    def can_execute(self, agent_name: str) -> bool:
        """检查是否允许执行"""
        state = self.get_state(agent_name)

        if state == CircuitState.OPEN:
            return False

        if state == CircuitState.HALF_OPEN:
            with self._lock:
                calls = self.half_open_calls.get(agent_name, 0)
                if calls >= self.half_open_max_calls:
                    return False
                self.half_open_calls[agent_name] = calls + 1

        return True

    def get_stats(self, agent_name: str) -> Dict[str, Any]:
        """获取熔断器统计"""
        with self._lock:
            return {
                "state": self.states.get(agent_name, CircuitState.CLOSED).value,
                "failure_count": self.failure_counts.get(agent_name, 0),
                "success_count": self.success_counts.get(agent_name, 0),
                "opened_at": self.opened_at.get(agent_name, 0)
            }


class FailoverManager:
    """
    故障转移管理器

    当主 Agent 失败时，自动切换到备用 Agent：
    1. 注册主备关系
    2. 主 Agent 失败时，路由到备用
    3. 支持多级故障转移（A -> B -> C）
    """

    def __init__(self):
        self.failover_chains: Dict[str, List[str]] = {}  # primary -> [backup1, backup2, ...]
        self.current_target: Dict[str, str] = {}  # task -> current_agent
        self._lock = threading.Lock()

    def register_failover(self, primary: str, backups: List[str]) -> None:
        """注册故障转移链"""
        with self._lock:
            self.failover_chains[primary] = backups
            logger.info(f"[FailoverManager] 注册故障转移: {primary} -> {backups}")

    def get_target(self, primary: str, health_checker: Callable[[str], bool]) -> str:
        """
        获取可用的目标 Agent

        Args:
            primary: 主 Agent 名称
            health_checker: 健康检查函数，返回 Agent 是否可用
        """
        with self._lock:
            # 先检查主 Agent
            if health_checker(primary):
                return primary

            # 主 Agent 不可用，检查备用
            backups = self.failover_chains.get(primary, [])
            for backup in backups:
                if health_checker(backup):
                    logger.warning(f"[FailoverManager] 主 Agent {primary} 不可用，切换到备用 {backup}")
                    return backup

            # 所有 Agent 都不可用
            logger.error(f"[FailoverManager] 主 Agent {primary} 和所有备用都不可用")
            return primary  # 返回主 Agent，让调用方处理失败

    def get_failover_chain(self, primary: str) -> List[str]:
        """获取故障转移链"""
        with self._lock:
            return [primary] + self.failover_chains.get(primary, [])


class ResilientAgentSwarm:
    """
    容错增强的 Agent 协作系统

    集成：
    - 心跳监控
    - 超时重试
    - 熔断器
    - 故障转移
    """

    def __init__(self, name: str = "resilient_swarm"):
        self.name = name
        self.heartbeat_monitor = HeartbeatMonitor()
        self.retry_policy = RetryPolicy()
        self.circuit_breaker = CircuitBreaker()
        self.failover_manager = FailoverManager()
        self.agents: Dict[str, Any] = {}

    def register_agent(self, name: str, agent_instance: Any,
                      backups: Optional[List[str]] = None) -> None:
        """注册 Agent"""
        self.agents[name] = agent_instance
        self.heartbeat_monitor.register(name)

        if backups:
            self.failover_manager.register_failover(name, backups)

    def call_agent_resilient(self, agent_name: str, prompt: str,
                            timeout: float = 10.0) -> Tuple[bool, Any, str]:
        """
        容错调用 Agent

        Returns:
            (success, result, details)
        """
        # 1. 检查熔断器
        if not self.circuit_breaker.can_execute(agent_name):
            stats = self.circuit_breaker.get_stats(agent_name)
            return False, None, f"[熔断] Agent {agent_name} 熔断器状态: {stats['state']}"

        # 2. 检查心跳
        health = self.heartbeat_monitor.get_health(agent_name)
        if health and health.status in [AgentStatus.FAILED, AgentStatus.UNRESPONSIVE]:
            # 尝试故障转移
            target = self.failover_manager.get_target(
                agent_name,
                lambda name: self._is_agent_healthy(name)
            )
            if target != agent_name:
                agent_name = target
                logger.info(f"[ResilientSwarm] 故障转移到: {agent_name}")

        # 3. 执行调用（带重试）
        def _do_call():
            agent = self.agents.get(agent_name)
            if not agent:
                raise Exception(f"Agent {agent_name} 未注册")

            # 模拟超时控制
            start = time.time()
            if hasattr(agent, 'run'):
                result = agent.run(prompt)
                return result.final_answer if hasattr(result, 'final_answer') else str(result)
            elif callable(agent):
                return str(agent(prompt))
            return str(agent)

        success, result, attempts = self.retry_policy.execute(_do_call)

        # 4. 记录结果
        if success:
            self.circuit_breaker.record_success(agent_name)
            health = self.heartbeat_monitor.get_health(agent_name)
            if health:
                health.total_calls += 1
                health.consecutive_failures = 0
                health.consecutive_successes += 1
            return True, result, f"[成功] 尝试 {attempts} 次"
        else:
            self.circuit_breaker.record_failure(agent_name)
            health = self.heartbeat_monitor.get_health(agent_name)
            if health:
                health.total_calls += 1
                health.failed_calls += 1
                health.consecutive_failures += 1
                health.consecutive_successes = 0
            return False, result, f"[失败] 尝试 {attempts} 次，错误: {result}"

    def _is_agent_healthy(self, name: str) -> bool:
        """检查 Agent 是否健康"""
        health = self.heartbeat_monitor.get_health(name)
        if not health:
            return False
        return health.status == AgentStatus.HEALTHY

    def start_monitoring(self) -> None:
        """启动监控"""
        self.heartbeat_monitor.start()

    def stop_monitoring(self) -> None:
        """停止监控"""
        self.heartbeat_monitor.stop()

    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        health_data = {}
        for name in self.agents:
            health = self.heartbeat_monitor.get_health(name)
            circuit_stats = self.circuit_breaker.get_stats(name)
            health_data[name] = {
                "health": health.to_dict() if health else {},
                "circuit": circuit_stats
            }
        return health_data