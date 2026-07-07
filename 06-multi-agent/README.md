# 06 多 Agent 协作（Multi-Agent）

## 定义

**多 Agent 协作**是指多个具有不同角色、能力或目标的 Agent 通过通信与协调，共同完成单一 Agent 难以胜任的复杂任务。关键在于如何分解任务、分配角色、管理通信和解决冲突。

核心概念：
- **角色（Role）**：每个 Agent 的专业定位（如研究员、写手、审查员、调度员）。
- **通信模式（Communication Pattern）**：集中式（通过调度员中转）、点对点（直接通信）、发布-订阅（广播）。
- **任务分解（Task Decomposition）**：将大任务拆分为子任务，分配给最适合的 Agent。
- **冲突解决（Conflict Resolution）**：当 Agent 之间结论矛盾时，如何仲裁或迭代达成共识。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_round_robin.py` | 轮流发言的极简多 Agent | `05-agent-core/skill/` |
| `demo/02_hierarchical.py` | 调度员 + 执行 Agent 的层级结构 | `05-agent-core/skill/` |
| `demo/03_debate.py` | 正反方辩论后总结 | `05-agent-core/skill/` |

### 核心代码片段

```python
# skill/agent_swarm.py 设计目标：轻量级多 Agent 编排框架
from typing import List, Dict, Any, Callable

class AgentSwarm:
    def __init__(self):
        self.agents: Dict[str, Any] = {}      # name -> agent_loop instance
        self.roles: Dict[str, str] = {}        # name -> role description

    def register(self, name: str, agent_loop, role: str):
        self.agents[name] = agent_loop
        self.roles[name] = role

    def run(self, task: str, pattern: str = "hierarchical") -> Dict[str, Any]:
        """
        pattern: hierarchical | round_robin | debate
        """
        if pattern == "hierarchical":
            return self._hierarchical_run(task)
        elif pattern == "round_robin":
            return self._round_robin_run(task)
        else:
            raise ValueError(f"Unknown pattern: {pattern}")

    def _hierarchical_run(self, task: str) -> Dict[str, Any]:
        # 1. 调度员分解任务
        # 2. 分发给执行 Agent
        # 3. 汇总结果
        pass
```

## 企业应用注意点

1. **通信风暴**：多 Agent 频繁通信可能导致消息爆炸和延迟激增。需限制通信轮次、采用批量汇总机制。
2. **一致性与共识**：不同 Agent 基于不同知识源可能给出矛盾结论。需设计明确的仲裁机制（如权威 Agent 裁决、投票、置信度排序）。
3. **身份与权限**：每个 Agent 应拥有独立的身份标识和权限边界。禁止低权限 Agent 冒充高权限 Agent 发起操作。
4. **调试复杂度**：多 Agent 系统的故障排查比单 Agent 困难得多。要求所有 Agent 间通信带全局 Trace ID，日志集中汇聚。
5. **成本线性增长**：Agent 数量增加通常意味着 LLM 调用次数线性或超线性增长。需评估任务是否真的需要多 Agent，或可通过单 Agent + 工具解决。

## 应用场景推演

### 场景：智能投研报告生成
投研任务复杂，可分解为：
1. **数据收集 Agent**：抓取财报、新闻、行业数据。
2. **分析 Agent**：财务分析、估值建模、风险评估。
3. **撰写 Agent**：整合分析结果，生成报告章节。
4. **审查 Agent**：检查数据一致性、合规用语、逻辑漏洞。

**注意点**：审查 Agent 发现数据矛盾时，需触发回溯（要求数据收集 Agent 重新核实），而非直接发布；最终报告需人工审批节点。

### 演进路径
- 当前层解决"多个 Agent 如何协作"。
- 下一章（07-workflow）将引入更结构化的编排方式，把协作模式固化为可复用工作流。
