# 01 基础与环境

## 定义

**Agent 开发基础**指运行 Agent 所需的最小环境单元：与大模型（LLM）建立连接、管理配置、记录日志与追踪请求。没有稳定的底座，上层所有能力都无法可靠运行。

核心概念：
- **LLM Client**：封装不同提供商（OpenAI、Anthropic、本地模型等）的统一调用接口。
- **Config Manager**：集中管理 API Key、模型参数、超时、重试策略。
- **Tracer**：记录输入输出、延迟、Token 消耗，为后续调试和成本分析提供数据。

## 示例

### Demo 列表

| Demo | 说明 | 运行方式 | 依赖 |
|------|------|----------|------|
| `demo/01_direct_llm_call.py` | 最简单的 LLM 调用，支持 OpenAI、智普、DeepSeek | `python demo/01_direct_llm_call.py` | `openai` |
| `demo/02_config_and_prompt.py` | 管理配置和 Prompt 模板，支持配置文件和环境变量 | `python demo/02_config_and_prompt.py` | `openai` |
| `demo/03_token_tracking_and_logging.py` | 记录 Token 消耗和日志，输出到控制台和文件 | `python demo/03_token_tracking_and_logging.py` | `openai` |
| `demo/04_config_layers_retry_budget.py` | 配置分层、超时重试、Token 预算管理和告警 | `python demo/04_config_layers_retry_budget.py` | `openai`, `requests` |
| `demo/05_framework_comparison.py` | 主流 LLM 框架对比分析（OpenAI SDK、LiteLLM、LangChain 等） | `python demo/05_framework_comparison.py` | 无 |

### 核心代码片段

```python
# skill/base_llm_client.py 设计目标：统一不同 LLM 的调用接口
from abc import ABC, abstractmethod
from typing import Iterator
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""

class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """同步完成，返回文本结果"""
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式返回 Token"""
        pass
```

### Demo 详解

#### Demo 1：直接调用 LLM
**目标**：展示最基础的 LLM 调用方式，支持多提供商。

**关键点**：
- 通过 `LLMConfig` 配置不同提供商的 API Key 和模型
- 支持同步调用 `complete()` 和流式调用 `stream()`
- 每个提供商有独立的 Client 实现，但接口统一

**运行前准备**：
```bash
export OPENAI_API_KEY=your-openai-key
export ZHIPU_API_KEY=your-zhipu-key
export DEEPSEEK_API_KEY=your-deepseek-key
```

---

#### Demo 2：管理配置和 Prompt
**目标**：展示配置分层和 Prompt 模板管理。

**关键点**：
- 配置优先级：默认值 < 配置文件 < 环境变量
- 使用 `PromptTemplate` 类管理模板文件
- 动态渲染模板变量，支持多种场景

**配置文件示例**（`demo/config.json`）：
```json
{
  "provider": "openai",
  "model": "gpt-3.5-turbo",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**Prompt 模板示例**（`demo/prompt_templates.json`）：
```json
{
  "analyze_text": "请分析以下文本：\n\n{text}\n\n分析结果：",
  "summarize": "请用不超过{max_length}字总结：\n\n{content}"
}
```

---

#### Demo 3：记录 Token 消耗和日志
**目标**：展示如何追踪每次 LLM 调用的详细信息。

**关键点**：
- 使用 `Tracer` 记录每次调用的 Trace ID、Token 消耗、延迟
- 输出结构化日志到控制台和文件
- 提供统计信息（调用次数、总 Token、平均延迟）

**日志格式**：
```
2024-01-01 12:00:00,000 - INFO - trace-id - LLM Call - Provider: openai, Model: gpt-3.5-turbo, Tokens: 100 (prompt=50, completion=50), Latency: 500.00ms
```

---

#### Demo 4：配置分层、超时重试、Token 预算管理
**目标**：展示企业级生产环境所需的核心能力。

**配置分层**：
```
默认值 (LLMConfig 类定义)
    ↓ 覆盖
配置文件 (config.json)
    ↓ 覆盖
环境变量 (LLM_* 前缀)
    ↓ 覆盖
代码传入参数 (最高优先级)
```

**超时重试策略**：
- 设置连接超时和读取超时
- 指数退避重试：失败后等待 1s、2s、4s... 后重试
- 最大重试次数可配置

**Token 预算管理**：
- 设置月度 Token 预算上限
- 超过阈值（默认 80%）时发出警告
- 耗尽预算时拒绝调用

---

#### Demo 5：框架对比分析
**目标**：对比市面上主流 LLM 框架的特点和适用场景。

**框架对比表**：

| 框架 | 特点 | 适用场景 |
|------|------|----------|
| OpenAI SDK | 官方支持，稳定可靠 | 快速原型、只使用 OpenAI |
| LiteLLM | 统一 API，支持 100+ 模型 | 多模型支持、成本优化 |
| LangChain | 组件丰富，支持 Agent/RAG | 复杂应用、组件组合 |
| LlamaIndex | 专注 RAG，数据连接能力强 | 文档问答、企业知识库 |
| FastChat | 支持模型部署，性能优化 | 自建对话服务 |
| 本项目 skill | 代码透明，易于理解 | 学习原理、小型项目 |

## 企业应用注意点

1. **密钥安全**：禁止将 API Key 硬编码到代码库。使用环境变量或企业密钥管理服务（如 AWS Secrets Manager、Azure Key Vault）。
2. **超时与重试**：生产环境必须配置连接超时、读取超时和指数退避重试，防止级联故障。
3. **成本控制**：记录每次调用的 Token 消耗，设置预算告警；对非必要场景启用缓存。
4. **可观测性**：接入企业统一的日志和监控体系（如 Prometheus + Grafana），关注 P95 延迟和错误率。
5. **多模型切换**：预留模型切换能力，以应对单点故障或不同任务的成本/效果权衡。
6. **配置管理**：使用配置分层机制，确保开发/测试/生产环境使用不同配置，通过环境变量覆盖敏感信息。
7. **审计日志**：所有 LLM 调用必须记录完整的审计日志，包括输入、输出、Token 消耗、调用时间，满足合规要求。

## 应用场景推演

### 场景：内部知识问答助手
某企业希望基于私有文档构建问答助手。在基础层，需要：
1. 统一封装内部部署的 LLM 和外部 SaaS LLM，方便 A/B 测试。
2. 所有请求带上 `trace_id`，与用户会话关联，便于审计。
3. 配置分层：开发/测试/生产使用不同模型和参数，通过环境变量切换。
4. 设置 Token 预算，防止意外超支。

**架构设计**：
```
用户输入 → Prompt 模板渲染 → LLM 调用（带重试和预算检查）→ 响应 → Tracer 记录
```

### 场景：智能客服系统
客服系统需要处理大量用户请求，在基础层需要：
1. 超时控制：避免慢请求阻塞客服队列。
2. 重试机制：网络抖动时自动重试，提升成功率。
3. 日志追踪：记录每次对话的详细信息，用于质量评估。
4. 多模型支持：简单问题用低成本模型，复杂问题用高性能模型。

**成本优化策略**：
- 设置 Token 预算和告警阈值
- 对高频简单问题使用缓存
- 根据问题复杂度动态选择模型

### 演进路径
- 当前层提供稳定的调用底座。
- 下一章（02-tool-use）将为底座增加"手脚"，使其能调用外部 API 和数据库。

## 依赖安装

```bash
cd 01-foundation
pip install openai requests
```

## 运行示例

```bash
# 设置 API Key
export LLM_API_KEY=your-api-key

# 运行 Demo 1
python demo/01_direct_llm_call.py

# 运行 Demo 2
python demo/02_config_and_prompt.py

# 运行 Demo 3
python demo/03_token_tracking_and_logging.py

# 运行 Demo 4
python demo/04_config_layers_retry_budget.py

# 运行 Demo 5
python demo/05_framework_comparison.py
```
