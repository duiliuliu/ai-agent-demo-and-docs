# skill: memory

## 设计目标

为 Agent 提供多层记忆能力，支持短期记忆、长期记忆、用户画像、向量化记忆，以及智能加载策略和 Token 预算管理。

## 模块清单

| 文件 | 职责 |
|------|------|
| `base_memory.py` | 抽象基类 `BaseMemory` + 数据结构 `MemoryEntry` |
| `short_term_memory.py` | 短期记忆：内存滑动窗口，Token 限制 |
| `long_term_memory.py` | 长期记忆：文件持久化，关键词搜索 |
| `user_profile.py` | 用户画像：基本信息/偏好/实体/标签 |
| `vector_memory.py` | 向量记忆：字符级分词，混合相似度搜索 |
| `memory_loader.py` | 加载决策器：FULL/PARTIAL/ON_DEMAND/CACHED/SKIP 策略 |
| `memory_injector.py` | 注入器：Token 预算管理，Prompt 上下文构建 |
| `memory_manager.py` | 管理器：统一管理四种记忆，STM→LTM 转换 |

## 加载时序

```
请求 → MemoryLoader.decide() → MemoryInjector.inject() → Prompt 上下文

加载顺序：
  1. 用户画像 (CACHED)     — 小而关键，会话内缓存
  2. 长期记忆 (PARTIAL)    — 取最近 N 条，不全量
  3. 向量记忆 (ON_DEMAND)  — 仅查询意图时触发
  4. 短期记忆 (FULL)       — 全量，放 Prompt 末尾（近因效应）
```

## 使用方式

```python
from skill import MemoryManager, MemoryLoader, MemoryInjector

mm = MemoryManager("user_001")
loader = MemoryLoader(total_token_budget=4000)
injector = MemoryInjector(mm, loader)

mm.set_profile("姓名", "张三", "basic_info")
mm.add_long_term("用户喜欢吃川菜")
mm.add_short_term("你好", "user")

result = injector.inject("推荐美食", conversation_round=0, is_new_session=True)
print(result["context"])
```

## 边界约束

- 向量记忆使用 TF-IDF，无语义理解；生产环境应替换为 Embedding 模型
- 长期记忆使用文件存储；多实例场景需换 Redis/DB + 乐观锁
- Token 估算为近似值（len/4）；精确值需使用 tiktoken 库
