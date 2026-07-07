# 07 工作流编排（Workflow）

## 定义

**工作流编排**是将 Agent 的执行过程建模为结构化流程（图、状态机、DAG），以显式控制执行顺序、分支条件和循环逻辑。相比自由循环，工作流提供更强的可预测性、可复现性和可视化能力。

核心概念：
- **DAG（有向无环图）**：节点表示任务/Agent，边表示依赖关系，无环保证流程可终止。
- **状态机（State Machine）**：定义有限状态和触发迁移的事件，适用于审批、交互式流程。
- **条件分支（Conditional Branching）**：根据运行时数据决定流程走向（如 if/else、switch）。
- **人工节点（Human-in-the-Loop）**：流程中必须等待人工确认或输入的节点。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_dag_workflow.py` | 线性 + 并行 DAG 执行 | `05-agent-core/skill/` |
| `demo/02_state_machine.py` | 审批状态流转 | `05-agent-core/skill/` |
| `demo/03_human_in_the_loop.py` | 等待人工确认的节点 | `05-agent-core/skill/` |

### 核心代码片段

```python
# skill/workflow_engine.py 设计目标：轻量级、可持久化的工作流引擎
from typing import Dict, Any, Callable, List
from dataclasses import dataclass, field

@dataclass
class Node:
    id: str
    type: str  # 'agent' | 'tool' | 'condition' | 'human' | 'start' | 'end'
    config: Dict[str, Any] = field(default_factory=dict)
    next_nodes: List[str] = field(default_factory=list)

class WorkflowEngine:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.context: Dict[str, Any] = {}

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def run(self, start_node_id: str, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        self.context = initial_context
        current = start_node_id
        while current and current in self.nodes:
            node = self.nodes[current]
            result = self._execute_node(node)
            self.context[f"result_{node.id}"] = result
            current = self._decide_next(node, result)
        return self.context

    def _execute_node(self, node: Node) -> Any:
        pass

    def _decide_next(self, node: Node, result: Any) -> str:
        pass
```

## 企业应用注意点

1. **流程版本控制**：工作流定义应作为代码版本管理，支持灰度发布和回滚。禁止在生产环境直接修改正在运行的工作流定义。
2. **持久化与恢复**：长周期工作流（含人工节点）必须持久化到数据库，支持服务重启后恢复状态，避免流程丢失。
3. **幂等性**：网络抖动或重试可能导致节点重复执行。关键节点（如扣款、发通知）必须保证幂等。
4. **可视化与监控**：企业需要看到当前有多少流程在跑、卡在哪个节点、平均耗时。工作流引擎应输出结构化事件供 BI 和运维使用。
5. **合规审计**：金融、医疗等行业要求流程可追溯。工作流需记录每个节点的输入输出、执行人、执行时间、决策依据。

## 应用场景推演

### 场景：信贷审批智能流程
信贷申请工作流：
1. **Start**：接收申请材料。
2. **Agent 初筛**：自动核验基本信息完整性（Agent 节点）。
3. **Condition**：信用评分 > 700？
   - 是 -> 进入快速通道。
   - 否 -> 进入人工复核通道。
4. **Agent 风控评估**：调用外部数据源评估风险（Agent 节点）。
5. **Human 节点**：信贷经理最终审批。
6. **End**：通知客户结果。

**注意点**：人工节点需设置 SLA（如 48 小时内必须处理），超时自动升级；风控评估节点必须引用可解释的数据来源，拒绝黑箱决策。

### 演进路径
- 当前层提供"结构化流程"。
- 下一章（08-enterprise）将补充企业级横切关注点：安全、权限、监控、RAG。
