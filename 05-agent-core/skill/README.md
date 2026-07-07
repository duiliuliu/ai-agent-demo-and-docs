# skill: agent_loop

## 设计目标

将 Observation、Thought、Action 组装成稳定、可观测、可中断的自闭环，是单 Agent 的运行时核心。

## 接口清单

| 文件 | 职责 |
|------|------|
| `agent_loop.py` | `AgentLoop` 主循环：组装各模块、控制生命周期 |
| `termination_checker.py` | 终止条件判定：完成、步数上限、人工中断、致命错误 |
| `context_manager.py` | 单次运行的上下文组装与快照 |

## 使用方式

```python
from skill.agent_loop import AgentLoop

loop = AgentLoop(
    llm_client=client,
    reasoning_engine=react_engine,
    tool_registry=registry,
    memory_store=memory,
    max_steps=10
)
result = loop.run("用户输入")
```

## 边界约束

- `agent_loop` 是 orchestrator，本身不包含业务逻辑。
- 所有外部能力通过构造函数注入，禁止在内部直接 import 具体实现。
- 单步异常必须被捕获并记录，不得中断整个循环（除非配置为致命错误）。
