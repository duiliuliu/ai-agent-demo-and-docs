# 02 工具调用（Tool Use / Function Calling）

## 定义

**工具调用**是指 Agent 在推理过程中，根据上下文判断需要调用外部函数或 API，将函数结果带回对话继续推理的能力。它是 Agent 从"纯文本生成"迈向"与环境交互"的关键一步。

核心概念：
- **Tool Schema**：用 JSON Schema 描述工具的名称、参数、类型和描述，供 LLM 理解。
- **Tool Registry**：工具的注册中心，支持动态注册、发现和调用。
- **Execution Engine**：实际执行工具调用的沙盒，负责参数解析、执行、错误捕获和结果格式化。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_define_tool.py` | 手动定义 Schema 并注册 | `01-foundation/skill/` |
| `demo/02_tool_loop.py` | LLM 判断调用 + 执行 + 续对话 | `01-foundation/skill/` |
| `demo/03_tool_error_handling.py` | 参数错误、执行失败时的容错 | `01-foundation/skill/` |

### 核心代码片段

```python
# skill/tool_registry.py 设计目标：让 LLM 能发现和安全调用工具
from typing import Callable, Any
import json

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, name: str, schema: dict, func: Callable):
        """注册工具：schema 供 LLM 使用，func 供本地执行"""
        self._tools[name] = func
        self._schemas[name] = schema

    def get_schemas(self) -> list[dict]:
        return list(self._schemas.values())

    def execute(self, name: str, arguments: dict) -> Any:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return self._tools[name](**arguments)
```

## 企业应用注意点

1. **权限最小化**：工具执行必须遵循最小权限原则。尤其是数据库查询、文件操作、发送邮件等工具，需接入企业统一权限体系。
2. **输入校验**：LLM 生成的参数不可信任。所有入参必须经过 Schema 校验和业务规则校验，防止注入或误操作。
3. **超时与熔断**：工具调用可能涉及外部 API，必须设置独立超时和熔断策略，避免阻塞 Agent 主循环。
4. **审计日志**：记录"调用了什么工具、传入什么参数、返回什么结果"，用于事后追溯和安全审计。
5. **工具版本管理**：工具 Schema 变更需兼容旧版本 Agent，避免已部署的 Agent 因 Schema 不匹配而失败。

## 应用场景推演

### 场景：智能客服工单系统
Agent 接收用户投诉后，需要：
1. 查询订单状态（调用订单 API）。
2. 若符合退款条件，创建退款工单（调用工单系统 API）。
3. 将处理结果通过邮件通知用户（调用邮件发送工具）。

**注意点**：订单 API 和工单 API 涉及敏感数据，必须校验 Agent 的身份和权限；邮件发送工具需要防滥用机制（如频率限制）。

### 演进路径
- 当前层让 Agent 拥有"手脚"。
- 下一章（03-memory）将解决 Agent"健忘"的问题，使其能记住对话历史和长期知识。
