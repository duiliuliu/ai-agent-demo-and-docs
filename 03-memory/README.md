# 03 记忆系统（Memory）

## 定义

**记忆系统**是 Agent 存储、检索和利用历史信息的能力。没有记忆，Agent 每次交互都是无状态的；有了记忆，Agent 才能理解上下文、积累经验、个性化回应。

核心概念：
- **短期记忆（Short-Term Memory, STM）**：当前会话的上下文窗口，通常以消息列表形式直接传入 LLM。
- **长期记忆（Long-Term Memory, LTM）**：跨会话保留的信息，如用户画像、历史决策、领域知识。
- **向量记忆（Vector Memory）**：将文本嵌入为向量，通过相似度检索召回相关内容，是 RAG 的基础。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_short_term_memory.py` | 基于列表的会话上下文管理 | `01-foundation/skill/` |
| `demo/02_long_term_memory.py` | 基于键值对的持久化记忆 | `01-foundation/skill/` |
| `demo/03_vector_memory.py` | 向量存储与相似度检索 | `01-foundation/skill/` |

### 核心代码片段

```python
# skill/memory_store.py 设计目标：统一不同记忆类型的读写接口
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MemoryStore(ABC):
    @abstractmethod
    def add(self, content: str, metadata: dict = None) -> None:
        pass

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """返回最相关的记忆片段，包含 content 和 score"""
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
```

## 企业应用注意点

1. **数据隐私**：用户对话可能包含敏感信息（PII）。长期记忆存储前需脱敏或加密；遵守 GDPR、个人信息保护法等合规要求。
2. **记忆生命周期**：定义记忆的过期和归档策略，避免存储无限增长导致成本飙升和检索质量下降。
3. **检索精度**：向量检索并非万能，需结合关键词过滤、元数据筛选和重排序（Rerank）提升召回准确率。
4. **多租户隔离**：SaaS 场景下，不同企业/用户的记忆必须物理或逻辑隔离，防止数据泄露。
5. **一致性**：分布式环境下，记忆的写入和读取需考虑最终一致性，避免 Agent 基于过时记忆做决策。

## 应用场景推演

### 场景：个性化销售助手
销售 Agent 服务多位客户，需要：
1. **短期记忆**：记住当前对话中客户提到的预算和 timeline。
2. **长期记忆**：记住该客户的历史偏好、成交记录、沟通风格。
3. **向量记忆**：从产品知识库中召回与客户需求最匹配的产品介绍。

**注意点**：客户信息属于商业机密，记忆存储必须加密；跨客户的数据严格隔离。

### 演进路径
- 当前层让 Agent"记得住"。
- 下一章（04-reasoning）将赋予 Agent"想得好"的能力，使其能分解复杂任务并规划执行步骤。
