# 05 Agent 核心循环（Agent Loop）

## 定义

**Agent 核心循环**是 Agent 持续运行的心脏。它将 Observation（观察）、Thought（思考）、Action（行动）串联成一个自闭环：Agent 观察环境/用户输入，思考下一步，执行行动，再根据行动结果继续观察，直到任务完成或达到终止条件。

核心概念：
- **Observation**：Agent 感知到的外部输入（用户消息、工具返回、系统事件）。
- **Thought**：Agent 对当前状态和目标的内部推理（由推理策略生成）。
- **Action**：Agent 对外部环境的输出（回复用户、调用工具、调用其他 Agent）。
- **Termination**：循环的退出条件（任务完成、达到最大步数、用户中断、发生致命错误）。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_basic_loop.py` | 最简 OTA 循环 | `01-foundation/skill/`, `04-reasoning/skill/` |
| `demo/02_loop_with_tools.py` | 带工具调用的循环 | 前序所有 skill/ |
| `demo/03_loop_with_memory.py` | 带记忆读写的循环 | 前序所有 skill/ |
| `demo/04_termination.py` | 多种终止条件处理 | 前序所有 skill/ |

### 核心代码片段

```python
# skill/agent_loop.py 设计目标：稳定、可观测、可中断的 Agent 主循环
from typing import Optional, Dict, Any

class AgentLoop:
    def __init__(self, llm_client, reasoning_engine, tool_registry, memory_store,
                 max_steps: int = 10):
        self.llm_client = llm_client
        self.reasoning = reasoning_engine
        self.tools = tool_registry
        self.memory = memory_store
        self.max_steps = max_steps

    def run(self, user_input: str) -> Dict[str, Any]:
        context = {"input": user_input, "steps": []}
        for step in range(self.max_steps):
            # 1. Observation
            obs = self._observe(context)
            # 2. Thought
            thought = self.reasoning.think(obs, context)
            # 3. Action
            action = self._decide_action(thought)
            if action["type"] == "finish":
                return self._finalize(context, action)
            result = self._execute(action)
            context["steps"].append({"obs": obs, "thought": thought, "action": action, "result": result})
        return self._finalize(context, {"type": "max_steps_reached"})
```

## 企业应用注意点

1. **超时控制**：Agent 循环可能因工具调用或推理陷入长时间等待。必须设置单步超时和总运行时间上限。
2. **资源限额**：限制循环的最大步数、单次 LLM 调用的 Token 上限、工具调用的并发数，防止资源耗尽。
3. **优雅中断**：提供人工介入和强制停止机制。对长循环任务，应允许用户随时中断并保留已执行步骤的结果。
4. **状态持久化**：对耗时任务，每一步的状态应持久化到数据库，支持断点续跑和事后审计。
5. **异常隔离**：单步失败不应导致整个 Agent 崩溃。需捕获异常、记录日志、向用户说明失败原因，并提供降级输出。

## 应用场景推演

### 场景：自动化运维排查
运维 Agent 接收告警后进入循环：
1. **Observation**：读取告警详情、最近日志。
2. **Thought**：分析可能原因（网络、磁盘、服务宕机）。
3. **Action**：调用日志查询工具、调用指标查询工具。
4. **Observation**：获取查询结果。
5. **Thought**：判断根因，决定是自动修复（重启服务）还是升级给值班人员。
6. **Termination**：修复成功或已通知人工。

**注意点**：自动修复工具（如重启服务）风险极高，必须双重确认（如要求 LLM 在 Thought 中明确说明理由，并匹配预定义的安全策略）；所有操作留痕。

### 演进路径
- 当前层完成了"一个 Agent"的核心。
- 下一章（06-multi-agent）将扩展为"多个 Agent"协作解决更复杂的问题。
