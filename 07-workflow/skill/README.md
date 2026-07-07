# skill: workflow_engine

## 设计目标

轻量级工作流引擎，支持 DAG、状态机和条件分支，将 Agent 执行固化为可预测、可持久化的结构化流程。

## 接口清单

| 文件 | 职责 |
|------|------|
| `workflow_engine.py` | 工作流执行引擎：节点调度、上下文传递、持久化钩子 |
| `node_definitions.py` | 节点类型定义：agent、tool、condition、human、start、end |
| `persistence_adapter.py` | 持久化适配器接口（内存/数据库/Redis） |

## 使用方式

```python
from skill.workflow_engine import WorkflowEngine
from skill.node_definitions import Node

engine = WorkflowEngine(persistence=redis_adapter)
engine.add_node(Node("start", "start", next_nodes=["agent_1"]))
engine.add_node(Node("agent_1", "agent", config={"agent": analyst_loop}, next_nodes=["end"]))
engine.add_node(Node("end", "end"))
result = engine.run("start", {"query": "月度销售数据"})
```

## 边界约束

- 工作流定义与执行引擎分离，支持从 JSON/YAML 加载流程定义。
- 人工节点（human）必须支持异步恢复，引擎不得阻塞等待。
