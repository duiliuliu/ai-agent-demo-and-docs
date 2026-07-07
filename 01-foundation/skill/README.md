# skill: base_llm_client

## 设计目标

提供统一、可替换的 LLM 调用接口，屏蔽不同提供商（OpenAI、Anthropic、本地模型）的差异。

## 接口清单

| 文件 | 职责 |
|------|------|
| `base_llm_client.py` | 抽象基类 `BaseLLMClient`，定义 `complete` / `stream` 接口 |
| `openai_client.py` | OpenAI API 实现 |
| `anthropic_client.py` | Anthropic API 实现 |
| `config_manager.py` | 配置加载与校验（环境变量 + 配置文件） |
| `tracer.py` | 请求追踪：trace_id、latency、token 消耗 |

## 使用方式

```python
from skill.base_llm_client import BaseLLMClient
from skill.openai_client import OpenAIClient

client: BaseLLMClient = OpenAIClient.from_config()
response = client.complete("Hello", temperature=0.7)
```

## 边界约束

- 禁止在 skill/ 内引入上层业务代码（如 tool、memory、agent_loop）。
- 所有实现类必须通过 `BaseLLMClient` 的接口暴露，外部不感知具体提供商。
