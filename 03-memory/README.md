# 03 记忆系统（Memory）

## 定义

**记忆系统**是 Agent 存储、检索和利用历史信息的能力。没有记忆，Agent 每次交互都是无状态的；有了记忆，Agent 才能理解上下文、积累经验、个性化回应。

## 核心架构

```
用户请求
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│                  MemoryLoader（加载决策器）                │
│  根据对话轮次/意图/记忆条目数，决策加载策略和时序          │
└────────────┬─────────────────────────────────────────────┘
             │ decisions
             ▼
┌──────────────────────────────────────────────────────────┐
│                  MemoryInjector（注入器）                  │
│  按决策执行加载 → Token 预算截断 → 拼接 Prompt 上下文       │
└──────┬───────────┬──────────┬──────────┬─────────────────┘
       │           │          │          │
  ┌────▼────┐ ┌───▼───┐ ┌───▼────┐ ┌───▼──────┐
  │用户画像  │ │长期记忆│ │向量记忆 │ │短期记忆   │
  │CACHED   │ │PARTIAL │ │ON_DEMAND│ │FULL     │
  │15%      │ │25%     │ │10%     │ │50%      │
  └─────────┘ └───────┘ └────────┘ └──────────┘
       │           │          │          │
       ▼           ▼          ▼          ▼
┌──────────────────────────────────────────────────────────┐
│                MemoryManager（记忆管理器）                  │
│  统一管理四种记忆，协调读写/更新/删除/STM→LTM转换          │
└──────────────────────────────────────────────────────────┘
```

## 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| BaseMemory | [base_memory.py](skill/base_memory.py) | 抽象基类，定义统一接口 |
| **EntityProfile** | [entity_profile.py](skill/entity_profile.py) | **泛化主体画像（用户/项目/产品/团队/场景）** |
| **UserProfile** | [user_profile.py](skill/user_profile.py) | 向后兼容的 UserProfile（EntityProfile 子类） |
| **ShortTermMemory** | [short_term_memory.py](skill/short_term_memory.py) | **会话段滚动+信息密度降噪（新版）** |
| **LongTermMemory** | [long_term_memory.py](skill/long_term_memory.py) | **集成 MemoryCompressor，自动去重/合并/覆盖** |
| **MemoryCompressor** | [memory_compressor.py](skill/memory_compressor.py) | **SKIP/MERGE/REPLACE/APPEND 四种决策** |
| VectorMemory | [vector_memory.py](skill/vector_memory.py) | 字符级分词，混合相似度搜索 |
| **MemoryLoader** | [memory_loader.py](skill/memory_loader.py) | 加载策略决策（FULL/PARTIAL/ON_DEMAND/CACHED/SKIP） |
| **MemoryInjector** | [memory_injector.py](skill/memory_injector.py) | Token 预算管理，Prompt 构建 |
| MemoryManager | [memory_manager.py](skill/memory_manager.py) | 统一管理，STM→LTM 转换 |

## 加载时序设计

**核心问题**：不是所有记忆都每次全量加载——那样 Token 消耗巨大且噪声多。

| 顺序 | 记忆类型 | 策略 | 触发条件 | Token 占比 |
|------|---------|------|---------|-----------|
| 1 | 用户画像 | CACHED | 新会话加载，后续缓存复用 | 15% |
| 2 | 长期记忆 | PARTIAL | 条目>N 取最近N条；≤N 全量 | 25% |
| 3 | 向量记忆 | ON_DEMAND | 检测到查询意图才触发搜索 | 10% |
| 4 | 短期记忆 | FULL | 每轮都加载，放 Prompt 末尾 | 50% |

**为什么短期记忆放最后？** LLM 注意力机制对 Prompt 末尾内容更敏感（近因效应）。

详见 [工程问题文档](docs/engineering_notes.md)。

## Demo 列表

| Demo | 说明 | 运行 |
|------|------|------|
| 01 | 短期记忆基础（会话段版） | `python demo/01_short_term_memory.py` |
| 02 | 长期记忆 CRUD + 搜索 | `python demo/02_long_term_memory.py` |
| 03 | 用户画像管理 | `python demo/03_user_profile.py` |
| 04 | 向量化记忆语义搜索 | `python demo/04_vector_memory.py` |
| 05 | 多记忆协同 + 多轮对话 | `python demo/05_memory_coordination.py` |
| 06 | 加载策略与时序演示 | `python demo/06_loading_strategy.py` |
| 07 | **泛化实体画像（用户/项目/产品）** | `python demo/07_entity_profile.py` |
| 08 | **长期记忆压缩与去噪** | `python demo/08_long_term_compression.py` |
| 09 | **短期记忆会话段降噪与滚动** | `python demo/09_short_term_segments.py` |

## 快速使用

```python
from skill import MemoryManager, MemoryLoader, MemoryInjector

# 初始化
mm = MemoryManager("user_001")
loader = MemoryLoader(total_token_budget=4000)
injector = MemoryInjector(mm, loader)

# 写入记忆
mm.set_profile("姓名", "张三", "basic_info")
mm.add_long_term("用户喜欢吃川菜")
mm.add_short_term("你好", "user")

# 加载并注入（自动决策加载策略）
result = injector.inject("推荐美食", conversation_round=0, is_new_session=True)
print(result["context"])       # 最终 Prompt 上下文
print(result["total_tokens"])  # Token 消耗
print(result["decisions"])     # 加载决策（含原因）
```

## 工程关注点

| 问题 | Demo方案 | 生产方案 | 文档 |
|------|---------|---------|------|
| **存储方案** | JSON文件+Python内存 | Redis+PostgreSQL+Milvus | [存储设计文档](docs/storage_design.md) |
| **中间件选择** | 零依赖 | Redis(短期)/PostgreSQL(长期)/Milvus(向量) | [存储设计文档](docs/storage_design.md) |
| **模型设计** | TF-IDF字符级分词 | Embedding(text-embedding-3-small)+Rerank | [存储设计文档](docs/storage_design.md) |
| **分布式一致性** | 文件存储(单机) | Redis+DB+乐观锁 | [工程问题文档第三章](docs/engineering_notes.md) |
| **向量检索准确性** | TF-IDF+余弦 | Embedding+Rerank | [工程问题文档第四章](docs/engineering_notes.md) |
| **Token预算管理** | 固定比例分配 | 动态调整+增量加载 | [工程问题文档第二章](docs/engineering_notes.md) |
| **记忆加载策略** | 5种策略 | +增量加载+异步预取 | [工程问题文档第五章](docs/engineering_notes.md) |
| **记忆更新覆盖** | 直接覆盖 | 版本化/LLM合并 | [工程问题文档第六章](docs/engineering_notes.md) |
| **STM→LTM转换** | 直接搬运 | LLM摘要压缩 | [工程问题文档第七章](docs/engineering_notes.md) |

## 演进路径

- 当前层让 Agent"记得住"。
- 下一章（04-reasoning）将赋予 Agent"想得好"的能力。
