"""
多 Agent 协作框架核心设计

## 协作模式分析

### 1. 平等协作模式（Peer-to-Peer Collaboration）
所有 Agent 平等地位，通过轮询或讨论方式协作。
适用场景：头脑风暴、共识达成、多角度分析问题。
特点：
  - 无中心调度
  - 每个 Agent 都有发言权
  - 通过消息传递协调

### 2. 主子模式（Hierarchical Collaboration）
一个主 Agent（调度员）分解任务，分配给子 Agent 执行，汇总结果。
适用场景：复杂任务需要统筹协调（如报告生成、项目分解）。
特点：
  - 主 Agent 拥有决策权
  - 子 Agent 只执行分配的任务
  - 结果汇总到主 Agent

### 3. 团队模式（Team Pipeline）
多个 Agent 按角色分工，形成流水线协作。
适用场景：内容创作（研究员→分析师→撰写员→审查员）。
特点：
  - 角色明确，职责分明
  - 前一个 Agent 的输出是下一个 Agent 的输入
  - 有明确的起点和终点

### 4. 辩论模式（Debate Collaboration）
正反方 Agent 辩论，第三方 Agent 总结。
适用场景：决策支持、利弊分析、风险评估。
特点：
  - 结构化辩论流程
  - 多轮交互
  - 最终由仲裁者总结

### 5. Agent 平台模式（Agent Platform）
Agent 自行注册到平台，动态发现和协作。
适用场景：开放环境、动态需求、未知协作关系。
特点：
  - 动态注册和发现
  - Agent 根据任务能力自行匹配
  - 平台提供通信基础设施

### 6. 竞争模式（Competition Collaboration）
多个 Agent 竞争完成同一任务，选出最优结果。
适用场景：方案设计、创意生成、需要多样化选项。
特点：
  - 并行执行
  - 由评估 Agent 或规则选出最优
  - 可以加权投票

## 通信方式分析

### 集中式通信（Centralized）
所有消息通过调度员中转。
优点：易于监控、便于仲裁、通信可控。
缺点：调度员压力大、延迟增加。

### 点对点通信（Peer-to-Peer）
Agent 之间直接通信。
优点：延迟低、效率高。
缺点：难以监控、可能消息风暴。

### 发布-订阅（Pub/Sub）
Agent 发布消息到主题，订阅者接收。
优点：灵活、支持广播。
缺点：消息可能泛滥、需要过滤机制。

### 共享黑板（Blackboard）
所有 Agent 访问共享状态空间。
优点：易于共享信息、支持增量式工作。
缺点：需要锁机制、可能有数据竞争。

## 企业工程关键问题

1. **通信风暴控制**：限制通信轮次、批量汇总、消息优先级
2. **一致性保证**：仲裁机制、投票、置信度排序
3. **身份与权限**：每个 Agent 有独立身份、权限边界
4. **全局追踪**：所有通信带 Trace ID，日志汇聚
5. **成本控制**：Agent 数量限制、通信轮次限制
6. **故障隔离**：单个 Agent 失败不影响整体
7. **负载均衡**：任务分配要考虑 Agent 能力
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Callable, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CollaborationPattern(Enum):
    """协作模式枚举"""
    ROUND_ROBIN = "round_robin"       # 轮流发言（平等协作）
    HIERARCHICAL = "hierarchical"     # 主子模式
    DEBATE = "debate"                 # 辩论模式
    TEAM_PIPELINE = "team_pipeline"   # 团队流水线
    AGENT_PLATFORM = "agent_platform" # Agent 平台
    COMPETITION = "competition"       # 竞争模式


class CommunicationMode(Enum):
    """通信模式枚举"""
    CENTRALIZED = "centralized"       # 集中式
    PEER_TO_PEER = "peer_to_peer"     # 点对点
    PUB_SUB = "pub_sub"               # 发布-订阅
    BLACKBOARD = "blackboard"         # 共享黑板


@dataclass
class AgentProfile:
    """Agent 身份档案"""
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0  # 优先级（用于竞争模式）
    max_concurrent_tasks: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "priority": self.priority
        }


@dataclass
class Message:
    """Agent 间通信消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str = ""  # 全局追踪ID
    sender: str = ""
    receiver: str = ""  # 可以是具体Agent名或"all"
    content: Any = None
    message_type: str = "task"  # task/result/query/notify/debate
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class TaskAssignment:
    """任务分配"""
    task_id: str
    description: str
    assigned_to: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    confidence: float = 0.0


@dataclass
class CollaborationResult:
    """协作执行结果"""
    trace_id: str
    pattern: CollaborationPattern
    success: bool
    final_output: Any
    agent_results: Dict[str, Any] = field(default_factory=dict)
    total_messages: int = 0
    total_rounds: int = 0
    execution_time_ms: float = 0.0
    cost_estimate: float = 0.0
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"协作模式: {self.pattern.value}",
            f"追踪ID: {self.trace_id}",
            f"执行状态: {'成功' if self.success else '失败'}",
            f"通信轮次: {self.total_rounds}",
            f"消息数量: {self.total_messages}",
            f"执行耗时: {self.execution_time_ms:.1f}ms",
            f"参与Agent: {len(self.agent_results)}",
            f"最终输出: {self.final_output[:200] if isinstance(self.final_output, str) else self.final_output}"
        ]
        if self.errors:
            lines.append(f"错误列表: {self.errors}")
        return "\n".join(lines)


class AgentSwarm:
    """
    多 Agent 协作编排框架
    
    核心能力：
    1. Agent 注册与管理
    2. 多种协作模式支持
    3. 通信总线管理
    4. 任务分解与分配
    5. 结果汇总与仲裁
    6. 全局追踪与观测
    """

    def __init__(
        self,
        name: str = "default_swarm",
        max_rounds: int = 10,
        max_messages_per_round: int = 50,
        communication_mode: CommunicationMode = CommunicationMode.CENTRALIZED
    ):
        self.name = name
        self.max_rounds = max_rounds
        self.max_messages_per_round = max_messages_per_round
        self.communication_mode = communication_mode

        self.agents: Dict[str, Any] = {}
        self.profiles: Dict[str, AgentProfile] = {}
        self.message_history: List[Message] = []
        self.blackboard: Dict[str, Any] = {}  # 共享状态

        self._trace_id: str = ""
        self._current_round: int = 0

    def register(
        self,
        name: str,
        agent_instance: Any,
        role: str,
        capabilities: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """注册 Agent 到协作系统"""
        self.agents[name] = agent_instance
        self.profiles[name] = AgentProfile(
            name=name,
            role=role,
            capabilities=capabilities or [role],
            priority=priority
        )
        logger.info(f"[AgentSwarm] 注册 Agent: {name}, 角色: {role}")

    def run(
        self,
        task: str,
        pattern: CollaborationPattern = CollaborationPattern.HIERARCHICAL,
        context: Optional[Dict[str, Any]] = None
    ) -> CollaborationResult:
        """执行协作任务"""
        self._trace_id = f"trace_{str(uuid.uuid4())[:8]}"
        self._current_round = 0
        self.message_history = []
        self.blackboard = {"task": task, "context": context or {}}

        start_time = time.time()
        result = CollaborationResult(
            trace_id=self._trace_id,
            pattern=pattern,
            success=False,
            final_output=None
        )

        try:
            logger.info(f"[AgentSwarm] 开始协作: 模式={pattern.value}, 任务={task[:50]}")

            if pattern == CollaborationPattern.ROUND_ROBIN:
                output = self._run_round_robin(task)
            elif pattern == CollaborationPattern.HIERARCHICAL:
                output = self._run_hierarchical(task)
            elif pattern == CollaborationPattern.DEBATE:
                output = self._run_debate(task)
            elif pattern == CollaborationPattern.TEAM_PIPELINE:
                output = self._run_team_pipeline(task)
            elif pattern == CollaborationPattern.COMPETITION:
                output = self._run_competition(task)
            else:
                raise ValueError(f"未支持的协作模式: {pattern}")

            result.success = True
            result.final_output = output

        except Exception as e:
            logger.error(f"[AgentSwarm] 协作执行异常: {e}")
            result.errors.append(str(e))

        result.total_messages = len(self.message_history)
        result.total_rounds = self._current_round
        result.execution_time_ms = (time.time() - start_time) * 1000
        result.agent_results = {name: self.blackboard.get(f"result_{name}") for name in self.agents}

        return result

    # ========== 协作模式实现 ==========

    def _run_round_robin(self, task: str) -> str:
        """平等协作模式：轮流发言"""
        all_outputs = []
        current_context = task

        for round_num in range(1, self.max_rounds + 1):
            self._current_round = round_num
            logger.info(f"[RoundRobin] 第 {round_num} 轮开始")

            for agent_name, agent in self.agents.items():
                # 每个 Agent 基于当前上下文发言
                response = self._call_agent(agent_name, agent, current_context)

                message = Message(
                    trace_id=self._trace_id,
                    sender=agent_name,
                    receiver="all",
                    content=response,
                    message_type="contribution"
                )
                self.message_history.append(message)

                all_outputs.append(f"[{agent_name}] {response}")
                current_context = f"{task}\n\n已有观点:\n" + "\n".join(all_outputs[-3:])

            # 检查是否达成共识（简单判断：最后几轮输出相似）
            if round_num >= 3:
                recent = all_outputs[-len(self.agents):]
                if self._check_consensus(recent):
                    logger.info(f"[RoundRobin] 第 {round_num} 轮达成共识")
                    break

        # 汇总结果
        return self._summarize_outputs(all_outputs)

    def _run_hierarchical(self, task: str) -> str:
        """主子模式：调度员分解任务，分配给子Agent执行"""
        # 找出主 Agent（通常是第一个注册的或标记为主调度）
        coordinator_name = list(self.agents.keys())[0]
        coordinator = self.agents[coordinator_name]

        logger.info(f"[Hierarchical] 主Agent: {coordinator_name}")

        # 主 Agent 分解任务
        decomposition_prompt = f"""请将以下任务分解为子任务，并指定执行每个子任务的Agent角色。
当前可用Agent: {list(self.profiles.keys())}

任务: {task}

请按以下格式输出：
子任务1: [描述] -> [Agent名]
子任务2: [描述] -> [Agent名]
..."""

        decomposition = self._call_agent(coordinator_name, coordinator, decomposition_prompt)

        # 解析子任务分配
        assignments = self._parse_task_assignments(decomposition)

        # 分发给各 Agent 执行
        results = {}
        for assignment in assignments:
            if assignment.assigned_to in self.agents:
                agent = self.agents[assignment.assigned_to]
                result = self._call_agent(assignment.assigned_to, agent, assignment.description)

                results[assignment.assigned_to] = result
                self.blackboard[f"result_{assignment.assigned_to}"] = result

                message = Message(
                    trace_id=self._trace_id,
                    sender=assignment.assigned_to,
                    receiver=coordinator_name,
                    content=result,
                    message_type="result"
                )
                self.message_history.append(message)

        # 主 Agent 汇总结果
        summary_prompt = f"""请汇总以下Agent的执行结果，生成最终输出：
{chr(10).join([f'{name}: {result}' for name, result in results.items()])}

原始任务: {task}"""

        final_output = self._call_agent(coordinator_name, coordinator, summary_prompt)
        return final_output

    def _run_debate(self, task: str) -> str:
        """辩论模式：正反方辩论，第三方总结"""
        # 需要至少3个Agent：正方、反方、仲裁
        if len(self.agents) < 3:
            return "辩论模式需要至少3个Agent（正方、反方、仲裁）"

        agent_names = list(self.agents.keys())
        proponent = agent_names[0]   # 正方
        opponent = agent_names[1]    # 反方
        judge = agent_names[2]       # 仲裁

        debate_history = []
        current_topic = task

        for round_num in range(1, min(self.max_rounds, 5) + 1):
            self._current_round = round_num

            # 正方发言
            pro_response = self._call_agent(
                proponent, self.agents[proponent],
                f"作为正方，请支持以下观点：{current_topic}\n历史辩论：{chr(10).join(debate_history)}"
            )
            debate_history.append(f"[正方-{proponent}] {pro_response}")
            self.message_history.append(Message(
                trace_id=self._trace_id,
                sender=proponent,
                receiver=opponent,
                content=pro_response,
                message_type="debate_pro"
            ))

            # 反方反驳
            opp_response = self._call_agent(
                opponent, self.agents[opponent],
                f"作为反方，请反驳正方的观点。\n正方观点：{pro_response}\n历史辩论：{chr(10).join(debate_history)}"
            )
            debate_history.append(f"[反方-{opponent}] {opp_response}")
            self.message_history.append(Message(
                trace_id=self._trace_id,
                sender=opponent,
                receiver=proponent,
                content=opp_response,
                message_type="debate_con"
            ))

        # 仲裁总结
        judge_response = self._call_agent(
            judge, self.agents[judge],
            f"作为仲裁者，请总结以下辩论，给出公正的结论：\n{chr(10).join(debate_history)}"
        )

        return f"辩论总结：{judge_response}"

    def _run_team_pipeline(self, task: str) -> str:
        """团队流水线模式：按角色顺序依次处理"""
        # Agent 按注册顺序形成流水线
        pipeline_order = list(self.agents.keys())

        current_input = task
        stage_outputs = {}

        for i, agent_name in enumerate(pipeline_order):
            self._current_round = i + 1
            agent = self.agents[agent_name]
            role = self.profiles[agent_name].role

            stage_prompt = f"""你是{role}，请处理以下输入：
{current_input}

请输出你的处理结果，供下一阶段使用。"""

            output = self._call_agent(agent_name, agent, stage_prompt)
            stage_outputs[agent_name] = output
            current_input = output

            self.message_history.append(Message(
                trace_id=self._trace_id,
                sender=agent_name,
                receiver="next_stage",
                content=output,
                message_type="pipeline_output"
            ))

            logger.info(f"[Pipeline] 阶段 {i+1} ({agent_name}) 完成")

        return current_input  # 流水线最后一个输出

    def _run_competition(self, task: str) -> str:
        """竞争模式：多个Agent并行执行，选出最优"""
        results = {}

        # 所有 Agent 并行执行（简化实现：顺序执行）
        for agent_name, agent in self.agents.items():
            self._current_round += 1
            result = self._call_agent(agent_name, agent, task)
            results[agent_name] = result

        # 按优先级或置信度选择最优
        best_agent = max(
            results.keys(),
            key=lambda name: self.profiles[name].priority
        )

        return f"最优方案（来自 {best_agent}）：{results[best_agent]}"

    # ========== 工具方法 ==========

    def _call_agent(self, name: str, agent: Any, prompt: str) -> str:
        """调用单个Agent"""
        logger.info(f"[AgentSwarm] 调用 Agent {name}: {prompt[:50] if len(prompt) > 50 else prompt}")
        
        try:
            # 如果 agent 有 run 方法（AgentLoop）
            if hasattr(agent, 'run') and callable(getattr(agent, 'run')):
                result = agent.run(prompt)
                if hasattr(result, 'final_answer'):
                    return result.final_answer
                return str(result)
            # 如果 agent 是函数
            elif callable(agent):
                return str(agent(prompt))
            else:
                return str(agent)
        except Exception as e:
            logger.error(f"[AgentSwarm] 调用 Agent {name} 失败: {e}")
            return f"[Agent {name} 执行错误]: {e}"

    def _check_consensus(self, outputs: List[str]) -> bool:
        """简单共识检测"""
        if len(outputs) < 2:
            return False
        # 检查最后几个输出是否都包含"同意"、"一致"等关键词
        consensus_keywords = ["同意", "一致", "共识", "agree", "consensus"]
        return any(
            any(keyword in output.lower() for keyword in consensus_keywords)
            for output in outputs[-2:]
        )

    def _summarize_outputs(self, outputs: List[str]) -> str:
        """汇总输出"""
        return "\n---\n".join(outputs[-len(self.agents):])

    def _parse_task_assignments(self, decomposition: str) -> List[TaskAssignment]:
        """解析任务分解结果"""
        assignments = []
        lines = decomposition.strip().split('\n')

        for i, line in enumerate(lines):
            if "->" in line or "：" in line or ":" in line:
                # 简单解析：提取描述和Agent名
                parts = line.replace("->", ":").split(":")
                if len(parts) >= 2:
                    description = parts[0].strip()
                    agent_name = parts[-1].strip()

                    assignments.append(TaskAssignment(
                        task_id=f"task_{i}",
                        description=description,
                        assigned_to=agent_name
                    ))

        # 如果解析失败，默认分配给所有Agent
        if not assignments:
            for name in self.agents.keys():
                assignments.append(TaskAssignment(
                    task_id=f"task_{name}",
                    description=f"执行任务的一部分",
                    assigned_to=name
                ))

        return assignments

    def get_message_trace(self) -> List[Dict[str, Any]]:
        """获取消息追踪记录"""
        return [msg.to_dict() for msg in self.message_history]

    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有Agent状态"""
        return {
            name: {
                "profile": profile.to_dict(),
                "blackboard_state": self.blackboard.get(f"result_{name}")
            }
            for name, profile in self.profiles.items()
        }