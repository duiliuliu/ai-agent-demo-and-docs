# 记忆存储方案与中间件选择

## 一、记忆存储方案设计

### 1.1 记忆类型与存储需求分析

| 记忆类型 | 特点 | 读写频率 | 生命周期 | 数据量 | 存储需求 |
|---------|------|---------|---------|--------|---------|
| 短期记忆 | 当前会话上下文 | 极高读/写 | 会话内（分钟级） | 中等（KB~MB） | 快速读写、自动过期 |
| 长期记忆 | 跨会话事实 | 读多写少 | 会话间（天/月级） | 大（MB~GB） | 持久化、可搜索 |
| 用户画像 | 用户基本信息 | 读多写少 | 用户级（长期） | 小（KB级） | 快速读取、原子更新 |
| 向量记忆 | 语义索引 | 写少搜多 | 会话间 | 大（MB~GB） | 向量索引、相似度搜索 |

### 1.2 存储方案映射

```
┌─────────────────────────────────────────────────────────────────┐
│                        存储架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  短期记忆     │     │  用户画像     │     │  长期记忆     │    │
│  │  Redis       │     │  Redis缓存    │     │  PostgreSQL  │    │
│  │  (TTL过期)    │     │  + MySQL持久化│     │  (事务保证)   │    │
│  └──────────────┘     └──────────────┘     └───────┬──────┘    │
│                                                     │           │
│                                                     ▼           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  向量数据库（Milvus/Chroma）              │   │
│  │              向量索引 + 元数据存储 + 相似度搜索           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 各记忆类型存储方案

#### 短期记忆存储
```python
# Redis 存储结构
# Key: session:{session_id}:stm
# Value: List[Dict] - 按顺序存储对话消息
# TTL: 会话超时（如 30 分钟）

# 写入
redis.rpush(f"session:{session_id}:stm", json.dumps({
    "role": "user",
    "content": "你好",
    "timestamp": "2024-01-01T10:00:00"
}))

# 读取（取最近 20 条）
redis.lrange(f"session:{session_id}:stm", -20, -1)

# 设置过期
redis.expire(f"session:{session_id}:stm", 30 * 60)
```

#### 用户画像存储
```python
# Redis 缓存（热点数据）
# Key: profile:{user_id}
# Value: JSON - 用户画像完整数据
# TTL: 1 小时（定期刷新）

# MySQL 持久化
# Table: user_profiles
# - user_id (PK)
# - basic_info (JSON)
# - preferences (JSON)
# - entities (JSON)
# - tags (JSON)
# - updated_at (TIMESTAMP)
```

#### 长期记忆存储
```python
# PostgreSQL 表结构
# Table: long_term_memories
# - id (SERIAL PK)
# - user_id (VARCHAR)
# - content (TEXT)
# - metadata (JSONB)
# - created_at (TIMESTAMP DEFAULT NOW())

# 索引优化
# - idx_user_id_created_at (user_id, created_at DESC)
# - idx_metadata (GIN on metadata)
```

#### 向量记忆存储
```python
# Milvus/Chroma 集合结构
# Collection: vector_memories
# - id (VARCHAR)
# - content (VARCHAR)
# - embedding (FLOAT_VECTOR)
# - metadata (JSON)
# - user_id (VARCHAR)

# 索引类型: HNSW
# 距离度量: COSINE
```

---

## 二、中间件选择对比

### 2.1 短期记忆存储对比

| 中间件 | 当前环境选择 | 线上推荐 | 优点 | 缺点 | 适用场景 |
|--------|-------------|---------|------|------|---------|
| **Python 内存** | ✅ | ❌ | 零延迟、无需依赖 | 重启丢失、单实例 | Demo/开发环境 |
| **Redis** | ❌ | ✅ | 高性能、TTL过期、分布式 | 需部署、有成本 | 生产环境 |
| **Memcached** | ❌ | ⚠️ | 简单、轻量 | 无持久化、无数据结构 | 不推荐 |
| **SQLite** | ❌ | ❌ | 文件存储、简单 | 性能一般、单进程 | 单机小应用 |

**推荐理由**：
- Redis 支持 List 数据结构，天然适合存储有序对话历史
- TTL 自动过期机制完美匹配短期记忆生命周期
- Redis Cluster 支持分布式部署，高可用

### 2.2 长期记忆存储对比

| 中间件 | 当前环境选择 | 线上推荐 | 优点 | 缺点 | 适用场景 |
|--------|-------------|---------|------|------|---------|
| **JSON 文件** | ✅ | ❌ | 零依赖、简单 | 性能差、无事务、单进程 | Demo/开发环境 |
| **PostgreSQL** | ❌ | ✅ | 事务保证、JSONB、全文搜索 | 部署复杂、运维成本 | 生产环境 |
| **MongoDB** | ❌ | ⚠️ | 文档型、灵活、水平扩展 | 事务支持弱、运维复杂 | 数据结构多变场景 |
| **MySQL** | ❌ | ⚠️ | 稳定、生态成熟 | JSON 支持一般、全文搜索弱 | 关系型数据为主 |

**推荐理由**：
- PostgreSQL 的 JSONB 类型完美支持记忆的元数据存储
- 内置全文搜索（tsvector/tsquery）可作为向量搜索的补充
- 事务保证确保记忆更新的原子性
- 生态成熟，运维工具丰富

### 2.3 用户画像存储对比

| 中间件 | 当前环境选择 | 线上推荐 | 优点 | 缺点 | 适用场景 |
|--------|-------------|---------|------|------|---------|
| **JSON 文件** | ✅ | ❌ | 零依赖 | 性能差、无缓存 | Demo/开发环境 |
| **Redis + MySQL** | ❌ | ✅ | 读写分离、高性能 | 双写一致性 | 生产环境 |
| **PostgreSQL** | ❌ | ⚠️ | 单一数据源、事务保证 | 读性能不如缓存 | 小规模应用 |
| **Cassandra** | ❌ | ⚠️ | 高可用、水平扩展 | 一致性弱、学习曲线 | 超大规模 |

**推荐理由**：
- 用户画像读多写少，Redis 缓存热数据
- MySQL/PostgreSQL 保证持久化和原子更新
- 缓存失效策略：用户修改画像时主动失效 + 定期刷新

### 2.4 向量记忆存储对比

| 中间件 | 当前环境选择 | 线上推荐 | 优点 | 缺点 | 适用场景 |
|--------|-------------|---------|------|------|---------|
| **TF-IDF + 文件** | ✅ | ❌ | 零依赖、简单 | 无语义理解、线性扫描 | Demo/开发环境 |
| **Milvus** | ❌ | ✅ | 专业向量数据库、高性能、分布式 | 部署复杂、运维成本 | 生产环境 |
| **Chroma** | ❌ | ⚠️ | 轻量、开源、易用 | 分布式支持弱、性能一般 | 中小规模 |
| **FAISS** | ❌ | ⚠️ | 高性能、Facebook 出品 | Python 绑定、无持久化 | 离线检索 |
| **Weaviate** | ❌ | ⚠️ | 多模态、GraphQL 查询 | 学习曲线、生态较小 | 多模态场景 |

**推荐理由**：
- Milvus 是专门为向量检索设计的数据库
- 支持 HNSW/IVF_FLAT 等多种索引类型
- 分布式部署、高可用、水平扩展
- 支持标量过滤 + 向量搜索混合查询

### 2.5 综合对比表

| 维度 | 当前环境（Demo） | 线上推荐（生产） |
|------|-----------------|-----------------|
| **短期记忆** | Python 内存 | Redis (TTL 30min) |
| **长期记忆** | JSON 文件 | PostgreSQL |
| **用户画像** | JSON 文件 | Redis 缓存 + MySQL/PostgreSQL |
| **向量记忆** | TF-IDF + 文件 | Milvus/Chroma |
| **部署方式** | 单机 | 分布式/集群 |
| **一致性** | 无 | 乐观锁 + 事务 |
| **可用性** | 单实例 | 多副本/主从 |
| **备份** | 无 | 定时备份 + 增量同步 |

---

## 三、模型设计

### 3.1 数据库模型设计

#### 用户画像表

```sql
-- MySQL/PostgreSQL
CREATE TABLE user_profiles (
    user_id VARCHAR(64) PRIMARY KEY,
    basic_info JSON NOT NULL DEFAULT '{}',
    preferences JSON NOT NULL DEFAULT '{}',
    entities JSON NOT NULL DEFAULT '{}',
    tags TEXT[] NOT NULL DEFAULT '{}',
    history JSON NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- PostgreSQL 索引
CREATE INDEX idx_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_profiles_updated_at ON user_profiles(updated_at DESC);
CREATE INDEX idx_profiles_tags ON user_profiles USING GIN(tags);
```

#### 长期记忆表

```sql
CREATE TABLE long_term_memories (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1
);

-- 索引
CREATE INDEX idx_ltm_user_id_created_at ON long_term_memories(user_id, created_at DESC);
CREATE INDEX idx_ltm_metadata ON long_term_memories USING GIN(metadata);
-- PostgreSQL 全文搜索索引
CREATE INDEX idx_ltm_content_tsv ON long_term_memories USING GIN(to_tsvector('chinese', content));
```

#### 短期记忆表（Redis 结构）

```
Key: session:{session_id}:stm
Value: List<JSON>

每条消息结构:
{
    "role": "user" | "assistant" | "system",
    "content": "消息内容",
    "timestamp": "ISO8601 时间戳",
    "token_count": 100
}
```

#### 向量记忆集合（Milvus）

```python
from pymilvus import connections, FieldSchema, CollectionSchema, DataType

# 连接 Milvus
connections.connect("default", host="milvus", port="19530")

# 定义字段
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
    FieldSchema(name="metadata", dtype=DataType.JSON),
    FieldSchema(name="created_at", dtype=DataType.INT64),
]

# 创建集合
schema = CollectionSchema(fields, description="向量记忆集合")
collection = Collection("vector_memories", schema)

# 创建索引
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 200}
}
collection.create_index("embedding", index_params)
```

### 3.2 Embedding 模型设计

#### 当前 Demo 模型（TF-IDF）

```python
# 当前实现：字符级分词 + 词频向量
# 优点：零依赖、简单
# 缺点：无语义理解、召回率低

def _tokenize(self, text: str) -> List[str]:
    tokens = []
    for char in text.lower():
        if '\u4e00' <= char <= '\u9fa5' or char.isalnum():
            tokens.append(char)
    return tokens
```

#### 生产环境推荐（Embedding 模型）

| 模型 | 维度 | 适用场景 | 优点 | 缺点 |
|------|------|---------|------|------|
| `text-embedding-3-small` | 1536 | 通用场景 | 高质量、多语言、更新快 | OpenAI 付费 |
| `text-embedding-ada-002` | 1536 | 通用场景 | 稳定、广泛使用 | 较旧 |
| `bge-large-zh` | 1024 | 中文场景 | 开源、中文优化、免费 | 需要部署 |
| `text2vec-base-chinese` | 768 | 中文场景 | 开源、轻量、中文优化 | 效果略差 |
| `m3e-large` | 1024 | 中文场景 | 开源、中文优化 | 需要部署 |

**模型选择建议**：
- **优先选择**：`text-embedding-3-small`（质量最高，多语言支持好）
- **成本敏感**：`bge-large-zh`（开源免费，中文效果好）
- **多模态**：考虑支持图像/音频的多模态 Embedding

#### 混合检索模型设计

```
┌─────────────────────────────────────────────────────────────┐
│                    混合检索架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户查询                                                    │
│    │                                                        │
│    ├──────────────────┬──────────────────────────────────┐   │
│    │                  │                                  │   │
│    ▼                  ▼                                  ▼   │
│  关键词搜索         向量搜索                            语义解析 │
│  (PostgreSQL        (Milvus)                           (LLM)  │
│   tsvector)         HNSW索引)                          提取实体) │
│    │                  │                                  │   │
│    └──────────────────┼──────────────────────────────────┘   │
│                       ▼                                      │
│                  结果合并                                     │
│                       │                                      │
│                       ▼                                      │
│                  Rerank                                     │
│              (cross-encoder)                                 │
│                       │                                      │
│                       ▼                                      │
│                  Top-K 结果                                   │
│                       │                                      │
│                       ▼                                      │
│                  注入 Prompt                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Rerank 模型设计

| 模型 | 用途 | 优点 | 缺点 |
|------|------|------|------|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 通用排序 | 开源、轻量、效果好 | 需要部署 |
| `text-rank-01` | OpenAI Rerank | 简单、无需部署 | 付费、延迟 |
| `bge-reranker-large` | 中文排序 | 开源、中文优化 | 需要部署 |

**Rerank 工作流程**：

```python
# 1. 向量检索召回 top-20
results = vector_db.search(query, top_k=20)

# 2. Cross-encoder 逐一打分
scores = rerank_model.predict([
    (query, item["content"]) for item in results
])

# 3. 按分数排序取 top-3
sorted_results = sorted(zip(results, scores), key=lambda x: -x[1])[:3]

# 4. 注入 Prompt
context = "\n".join([r[0]["content"] for r in sorted_results])
```

### 3.4 记忆更新模型设计

#### 版本化更新

```sql
-- 更新时版本号 +1
UPDATE long_term_memories 
SET content = '新内容', version = version + 1, updated_at = NOW()
WHERE id = 1 AND version = 3;

-- 如果 version 不匹配，更新失败（乐观锁）
```

#### 冲突检测

```python
def update_memory(user_id, memory_id, new_content):
    # 读取当前版本
    current = db.get_memory(memory_id)
    
    # 检查是否被其他实例修改
    if current.version != expected_version:
        # 冲突：需要重新读取并合并
        merged = llm.merge_memories(current.content, new_content)
        db.update_memory(memory_id, merged, current.version + 1)
        return merged
    else:
        # 无冲突：直接更新
        db.update_memory(memory_id, new_content, current.version + 1)
        return new_content
```

---

## 四、部署架构建议

### 4.1 开发环境（当前）

```
┌─────────────────────────────────────────────┐
│               开发环境                       │
├─────────────────────────────────────────────┤
│                                             │
│  Agent 进程                                  │
│    │                                        │
│    ├── 短期记忆 → Python 内存                │
│    ├── 长期记忆 → JSON 文件                  │
│    ├── 用户画像 → JSON 文件                  │
│    └── 向量记忆 → TF-IDF + JSON 文件         │
│                                             │
└─────────────────────────────────────────────┘
```

### 4.2 生产环境

```
┌──────────────────────────────────────────────────────────────┐
│                      生产环境                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │  Agent 实例1 │    │  Agent 实例2 │    │  Agent 实例N │      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                   Redis Cluster                      │     │
│  │  - 短期记忆（List + TTL）                            │     │
│  │  - 用户画像缓存（JSON + TTL）                        │     │
│  │  - 会话状态管理                                       │     │
│  └─────────────────────────────────────────────────────┘     │
│                            │                                  │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                PostgreSQL Cluster                    │     │
│  │  - 用户画像持久化                                    │     │
│  │  - 长期记忆存储（含全文搜索索引）                      │     │
│  │  - 事务保证                                         │     │
│  └─────────────────────────────────────────────────────┘     │
│                            │                                  │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                  Milvus Cluster                      │     │
│  │  - 向量索引（HNSW）                                  │     │
│  │  - 相似度搜索（COSINE）                              │     │
│  │  - 分布式向量存储                                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 中间件资源配置建议

| 中间件 | 开发环境 | 测试环境 | 生产环境（最小） | 生产环境（标准） |
|--------|---------|---------|-----------------|-----------------|
| **Redis** | 1 核 / 512MB | 2 核 / 2GB | 4 核 / 8GB | 8 核 / 32GB |
| **PostgreSQL** | 1 核 / 1GB | 2 核 / 4GB | 4 核 / 16GB | 8 核 / 64GB |
| **Milvus** | 1 核 / 2GB | 3 核 / 8GB | 8 核 / 32GB | 16 核 / 128GB |

### 4.4 监控与告警

```
监控指标：
- Redis: 内存使用、命中率、连接数、TTL 命中率
- PostgreSQL: 查询延迟、连接数、锁等待、索引使用率
- Milvus: 查询延迟、召回率、索引构建时间、QPS

告警规则：
- Redis 内存 > 80%
- PostgreSQL 查询延迟 > 500ms
- Milvus 查询延迟 > 200ms
- 记忆写入失败率 > 1%
```

---

## 五、数据迁移方案

### 5.1 从 Demo（文件）迁移到生产（数据库）

```python
# 迁移脚本示例

def migrate_long_term_to_postgres():
    # 读取 JSON 文件
    with open("data/long_term_memory.json", "r") as f:
        data = json.load(f)
    
    # 写入 PostgreSQL
    for entry in data["entries"]:
        db.execute("""
            INSERT INTO long_term_memories (user_id, content, metadata, created_at)
            VALUES (%s, %s, %s, %s)
        """, (
            "default_user",
            entry["content"],
            json.dumps(entry.get("metadata", {})),
            entry["timestamp"]
        ))
```

### 5.2 向量索引重建

```python
def rebuild_vector_index():
    # 从 PostgreSQL 读取所有长期记忆
    memories = db.query("SELECT * FROM long_term_memories")
    
    # 批量向量化
    batch_size = 100
    for i in range(0, len(memories), batch_size):
        batch = memories[i:i+batch_size]
        contents = [m["content"] for m in batch]
        embeddings = embedding_model.encode(contents)
        
        # 写入 Milvus
        entities = [
            m["id"], m["user_id"], m["content"], emb[j], m["metadata"], m["created_at"]
            for j, m in enumerate(batch)
        ]
        milvus_collection.insert(entities)
```
