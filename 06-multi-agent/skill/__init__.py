"""
06-multi-agent 模块

多 Agent 协作框架，支持多种协作模式和通信方式。
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
    AsyncBroadcastBus,
    FastChannelBus,
    create_bus
)
from .agent_monitor import (
    HeartbeatMonitor,
    RetryPolicy,
    CircuitBreaker,
    FailoverManager,
    ResilientAgentSwarm,
    AgentStatus,
    CircuitState
)

__all__ = [
    "AgentSwarm", "AgentProfile", "Message", "TaskAssignment",
    "CollaborationResult", "CollaborationPattern", "CommunicationMode",
    "CentralizedBus", "DirectBus", "PubSubBus", "BlackboardBus",
    "AsyncBroadcastBus", "FastChannelBus", "create_bus",
    "HeartbeatMonitor", "RetryPolicy", "CircuitBreaker",
    "FailoverManager", "ResilientAgentSwarm", "AgentStatus", "CircuitState"
]