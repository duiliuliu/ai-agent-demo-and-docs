# skill: reasoning

## 设计目标

为 Agent 提供多种推理方式（CoT/ReAct/Plan-and-Solve），按需选择最优策略。

## 模块清单

| 文件 | 职责 |
|------|------|
| `base_reasoner.py` | 抽象基类 + Step/ReasoningResult 数据结构 |
| `cot_reasoner.py` | CoT 思维链推理（1次LLM调用） |
| `react_reasoner.py` | ReAct 思考+行动循环（LLM+工具） |
| `plan_solve_reasoner.py` | Plan-and-Solve 规划+求解+验证 |
| `reasoning_router.py` | 推理路由 + ToolRegistry |

## 三种推理方式

```
CoT:           Q → [Thought1, Thought2, ...] → A
ReAct:         Q → [T-A-O]×N → A
Plan-and-Solve: Q → Plan → [Solve1, Solve2, ...] → Verify → A
```

## 使用方式

```python
from skill import ReasoningRouter, ToolRegistry

router = ReasoningRouter()
router.register_tool("get_weather", get_weather, "查询天气")

result = router.reason(
    user_input="北京今天天气怎么样？",
    intent="weather_query"
)
print(result.final_answer)
print(result.trace())  # 推理轨迹
```

## 路由决策

| 意图 | 推理方式 | LLM 调用 |
|------|---------|---------|
| greeting/thanks | NONE | 0 |
| qa/math/logic | CoT | 1 |
| weather/search/calc | ReAct | N |
| travel/research | Plan-Solve | N+2 |

## 边界约束

- LLM 客户端可插拔（None 时使用 mock）
- max_steps 限制防止死循环
- 工具调用失败有错误处理
