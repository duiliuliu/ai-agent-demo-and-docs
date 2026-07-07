# skill: agent_swarm

## 设计目标

轻量级多 Agent 编排框架，支持角色定义、通信模式选择和任务分发，将多个 `agent_loop` 实例组合为协作系统。

## 接口清单

| 文件 | 职责 |
|------|------|
| `agent_swarm.py` | 多 Agent 编排入口：注册、运行、模式选择 |
| `communication_bus.py` | 通信总线：集中式 / 点对点 / 广播消息传递 |
| `task_decomposer.py` | 任务分解器：将大任务拆分为子任务并匹配 Agent |

## 使用方式

```python
from skill.agent_swarm import AgentSwarm

swarm = AgentSwarm()
swarm.register("researcher", researcher_loop, role="数据收集")
swarm.register("writer", writer_loop, role="报告撰写")
result = swarm.run("生成一份行业分析报告", pattern="hierarchical")
```

## 边界约束

- 每个 Agent 必须是独立的 `agent_loop` 实例，禁止共享可变状态。
- 通信总线只传递序列化消息，不传递对象引用，避免分布式部署时的序列化问题。
