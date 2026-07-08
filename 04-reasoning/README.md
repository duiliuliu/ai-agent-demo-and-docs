# 04 推理系统（Reasoning）

## 定义

**推理系统**是 Agent 拆解复杂问题、规划执行步骤、动态决策的能力。仅有工具调用是"按指令行动"，加上推理才能"主动思考"。

三种核心推理方式：
- **CoT (Chain of Thought)**：单次LLM调用 + 逐步思考
- **ReAct (Reasoning + Acting)**：思考 → 行动 → 观察 的循环
- **Plan-and-Solve**：先规划后执行

## 架构设计

```
用户输入
  │
  ▼
[02-tool-use] IntentRecognizer → intent
  │
  ▼
┌────────────────────────────────────────────────────┐
│              ReasoningRouter（推理路由）             │
│  根据 intent 自动选择最合适的推理方式                  │
└────┬──────────────┬──────────────┬─────────────────┘
     │              │              │
     ▼              ▼              ▼
  ┌──────┐    ┌────────┐    ┌──────────────┐
  │ CoT  │    │ ReAct  │    │ Plan&Solve   │
  │ 1次  │    │ N次    │    │ 1+N+1次      │
  │ LLM  │    │ LLM+工具│    │ LLM          │
  └──────┘    └────────┘    └──────────────┘
     │              │              │
     └──────────────┴──────────────┘
                    │
                    ▼
           ReasoningResult
           (steps + final_answer)
```

## 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| BaseReasoner | [base_reasoner.py](skill/base_reasoner.py) | 推理器基类，定义统一接口 |
| Step / ReasoningResult | [base_reasoner.py](skill/base_reasoner.py) | 步骤和结果数据结构 |
| CoTReasoner | [cot_reasoner.py](skill/cot_reasoner.py) | 思维链推理 |
| ReActReasoner | [react_reasoner.py](skill/react_reasoner.py) | 思考+行动循环 |
| PlanAndSolveReasoner | [plan_solve_reasoner.py](skill/plan_solve_reasoner.py) | 规划+求解+验证 |
| ReasoningRouter | [reasoning_router.py](skill/reasoning_router.py) | 推理路由 + 工具管理 |
| ToolRegistry | [reasoning_router.py](skill/reasoning_router.py) | 工具注册器 |

## 三种推理方式对比

| 维度 | CoT | ReAct | Plan-and-Solve |
|------|-----|-------|----------------|
| LLM调用 | 1次 | N次 | 1+N+1次 |
| 工具调用 | 0次 | N次 | 0~N次 |
| 适用场景 | 数学/逻辑/解释 | 实时查询/工具交互 | 复杂规划/多步任务 |
| 优点 | 快、省、可解释 | 灵活、可与外部交互 | 结构化、可审核 |
| 局限 | 不能查外部信息 | 可能死循环 | 计划可能不准确 |

## 加载路由策略

| 意图类型 | 推理方式 | 典型场景 |
|---------|---------|---------|
| greeting / thanks | NONE | 闲聊/致谢 |
| qa / math / logic | CoT | 简单问答 |
| weather / search / calculation | ReAct | 工具查询 |
| travel_plan / research / complex | Plan-and-Solve | 复杂任务 |

## Demo 列表

| Demo | 说明 | 运行 |
|------|------|------|
| 01 | CoT 推理（数学/逻辑） | `python demo/01_cot_reasoning.py` |
| 02 | ReAct 推理（工具调用） | `python demo/02_react_reasoning.py` |
| 03 | Plan-and-Solve 推理 | `python demo/03_plan_solve_reasoning.py` |
| 04 | 多轮会话中的推理 | `python demo/04_multi_turn_reasoning.py` |
| 05 | 意图驱动的推理路由（进阶） | `python demo/05_intent_driven_routing.py` |

## 快速使用

```python
from skill import ReasoningRouter, ToolRegistry

# 创建路由
router = ReasoningRouter()

# 注册工具
def get_weather(params):
    return f"{params.get('city')} 28度 晴"

router.register_tool("get_weather", get_weather, "查询天气")

# 一站式推理
result = router.reason(
    user_input="北京今天天气怎么样？",
    intent="weather_query"  # 来自 02-tool-use
)

print(result.final_answer)    # 最终答案
print(result.trace())         # 推理轨迹
print(f"LLM调用: {result.total_llm_calls}, 工具调用: {result.total_tool_calls}")
```

## 工程关注点

| 问题 | 解决方案 | 文档 |
|------|---------|------|
| 死循环 | 连续3步同action强制停止 + max_steps限制 | [工程文档第2.1节](docs/engineering_notes.md) |
| 成本控制 | 路由选择（NONE < CoT < ReAct < Plan-Solve） | [工程文档第2.2节](docs/engineering_notes.md) |
| 可解释性 | trace() 输出步骤 + 计划可审核 | [工程文档第2.3节](docs/engineering_notes.md) |
| 工具选择 | 清晰工具描述 + Few-shot + 校验 | [工程文档第2.4节](docs/engineering_notes.md) |
| 状态管理 | 会话级Reasoner + 上下文传递 | [工程文档第2.5节](docs/engineering_notes.md) |
| 超时 | 多级限制（步数/时间）+ 降级策略 | [工程文档第2.6节](docs/engineering_notes.md) |
| 结果合并 | Self-Consistency + 置信度评分 | [工程文档第2.7节](docs/engineering_notes.md) |

## 监控指标

- **性能**：成功率、平均LLM调用次数、平均工具调用次数、延迟分布
- **质量**：答案准确率、工具选择正确率、用户满意度
- **成本**：单次推理成本、推理方式分布、Token使用

## 与前几章的联动

| 章节 | 联动方式 |
|------|---------|
| 01-foundation | LLM客户端统一接入 |
| 02-tool-use | IntentRecognizer → ReasoningRouter → 工具调用 |
| 03-memory | 推理时加载记忆，推理结果入记忆 |
| **05-（下一章）** | 推理结果驱动行动 |

## 演进路径

- 当前层让 Agent"想得好"。
- 下一章将让 Agent 基于推理结果"做得好"（行动执行）。
