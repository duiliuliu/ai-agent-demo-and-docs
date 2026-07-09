"""
06-multi-agent 模块

多 Agent 协作框架，支持多种协作模式和通信方式。

协作模式：
- ROUND_ROBIN: 平等协作，轮流发言
- HIERARCHICAL: 主子模式，调度员分配任务
- DEBATE: 辩论模式，正反方辩论后总结
- TEAM_PIPELINE: 团队流水线，按角色依次处理
- COMPETITION: 竞争模式，选出最优方案

通信方式：
- centralized: 集中式通信
- peer_to_peer: 点对点通信
- pub_sub: 发布订阅
- blackboard: 共享黑板
"""
from .agent_swarm import (
    AgentSwarm,
    AgentProfile,
    Message,
    TaskAssignment,
    CollaborationResult,
    CollaborationPattern,
    CommunicationMode
)
from .communication_bus import (
    CentralizedBus,
    DirectBus,
    PubSubBus,
    BlackboardBus,
    create_bus
)

__all__ = [
    "AgentSwarm",
    "AgentProfile",
    "Message",
    "TaskAssignment",
    "CollaborationResult",
    "CollaborationPattern",
    "CommunicationMode",
    "CentralizedBus",
    "DirectBus",
    "PubSubBus",
    "BlackboardBus",
    "create_bus"
]