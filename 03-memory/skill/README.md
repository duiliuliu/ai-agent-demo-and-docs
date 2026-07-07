# skill: memory_store

## 设计目标

为 Agent 提供统一的记忆读写接口，支持短期记忆（会话上下文）、长期记忆（键值持久化）和向量记忆（语义检索）。

## 接口清单

| 文件 | 职责 |
|------|------|
| `memory_store.py` | 抽象基类 `MemoryStore` |
| `short_term_memory.py` | 基于列表的滑动窗口上下文管理 |
| `long_term_memory.py` | 基于文件/数据库的键值持久化 |
| `vector_memory.py` | 向量存储 + 相似度检索（可对接 FAISS、Chroma 等） |

## 使用方式

```python
from skill.memory_store import MemoryStore
from skill.short_term_memory import ShortTermMemory

mem: MemoryStore = ShortTermMemory(max_messages=10)
mem.add("用户问：今天天气如何？")
context = mem.retrieve("天气", top_k=3)
```

## 边界约束

- 向量记忆的嵌入模型应可配置，禁止硬编码单一模型。
- 长期记忆需支持异步写入，避免阻塞 Agent 主循环。
