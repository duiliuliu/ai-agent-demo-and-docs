# skill: reasoning_engine

## 设计目标

提供可插拔的推理策略，使 Agent 能够根据任务复杂度选择不同的思考方式（CoT、ReAct、Plan-and-Solve）。

## 接口清单

| 文件 | 职责 |
|------|------|
| `reasoning_engine.py` | 抽象基类 `ReasoningEngine` |
| `cot_engine.py` | Chain-of-Thought 实现 |
| `react_engine.py` | ReAct 推理-行动循环实现 |
| `plan_and_solve_engine.py` | 先规划后执行实现 |

## 使用方式

```python
from skill.reasoning_engine import ReasoningEngine
from skill.react_engine import ReActEngine

engine: ReasoningEngine = ReActEngine(llm_client, tool_registry)
steps = engine.think("帮我订一张去上海的机票", context={})
```

## 边界约束

- 推理引擎只负责生成 Thought / Plan，不直接执行工具或修改记忆。
- 需接受 `llm_client: BaseLLMClient` 作为依赖注入，禁止内部实例化具体客户端。
