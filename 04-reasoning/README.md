# 04 推理策略（Reasoning）

## 定义

**推理策略**是指 Agent 在行动前进行结构化思考的方法。单纯依赖 LLM 的直觉生成容易出错，显式推理能让 Agent 分解复杂问题、检查中间步骤、修正错误，从而提升可靠性和可解释性。

核心概念：
- **CoT（Chain-of-Thought）**：要求 LLM 显式输出思考过程，再给出答案，适用于数学、逻辑题。
- **ReAct（Reasoning + Acting）**：将推理（Thought）和行动（Action）交错进行，Agent 根据观察结果动态调整下一步。
- **Plan-and-Solve**：先制定完整计划，再按步骤执行，适用于多步骤、依赖关系明确的任务。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_cot_basic.py` | 零样本 CoT 提示 | `01-foundation/skill/` |
| `demo/02_react_loop.py` | ReAct 推理-行动循环 | `01-foundation/skill/`, `02-tool-use/skill/` |
| `demo/03_plan_and_solve.py` | 先规划后执行 | `01-foundation/skill/`, `02-tool-use/skill/` |

### 核心代码片段

```python
# skill/reasoning_engine.py 设计目标：可插拔的推理策略引擎
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ReasoningEngine(ABC):
    @abstractmethod
    def think(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        返回思考步骤列表，每个步骤包含：
        - thought: 当前思考内容
        - action: 下一步行动（可选）
        - observation: 行动后的观察（由外部填充）
        """
        pass
```

## 企业应用注意点

1. **可解释性**：推理过程是 Agent 可解释性的核心。生产环境应保留 Thought 日志，便于业务人员理解 Agent 为何做出某决策。
2. **成本权衡**：显式推理会增加 Token 消耗和延迟。对简单任务可降级为直接生成；对关键任务强制使用 ReAct 或 Plan-and-Solve。
3. **错误回退**：推理链中某一步失败时，需设计回退策略（如重试、人工介入、切换到备用方案），而非让 Agent 无限循环。
4. **提示词工程**：推理策略高度依赖提示词模板。需建立提示词版本管理和 A/B 测试机制，避免未经测试的提示词上线。
5. **幻觉控制**：LLM 可能在推理过程中虚构事实。对关键推理步骤，要求引用可信来源（如知识库、工具返回结果）。

## 应用场景推演

### 场景：合规审查 Agent
企业合同审查需要多步推理：
1. **Plan**：先识别合同类型，再提取关键条款，最后逐条比对合规规则。
2. **ReAct**：若某条款模糊，调用法律数据库查询判例；根据查询结果决定是标记风险还是继续审查。
3. **CoT**：在输出最终审查意见前，要求 LLM 逐步说明每条风险的依据。

**注意点**：法律领域容错率极低，所有推理步骤和依据必须留痕，供律师复核；幻觉可能导致法律风险，关键判断必须引用真实条款。

### 演进路径
- 当前层让 Agent"想得好"。
- 下一章（05-agent-core）将把推理、工具、记忆组合成完整的 Agent 运行循环。
