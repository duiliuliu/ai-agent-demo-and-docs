# skill: tool_registry

## 设计目标

让 LLM 能够安全地发现、理解和调用外部工具。提供工具注册、Schema 生成、执行隔离和错误封装能力。

## 接口清单

| 文件 | 职责 |
|------|------|
| `tool_registry.py` | 工具注册中心：注册、发现、执行 |
| `tool_schema_builder.py` | 从 Python 函数自动生成 JSON Schema |
| `tool_executor.py` | 沙盒执行：超时控制、异常捕获、结果格式化 |

## 使用方式

```python
from skill.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register("get_weather", schema, get_weather_func)
schemas = registry.get_schemas()  # 传给 LLM
result = registry.execute("get_weather", {"city": "Beijing"})
```

## 边界约束

- 工具执行失败时，返回结构化错误信息（而非抛出裸异常），便于 LLM 理解并修复。
- 不依赖具体 LLM 实现，仅与 `01-foundation/skill/base_llm_client` 的接口类型交互（如需）。
