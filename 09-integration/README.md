# 09 综合实战（Integration）

## 定义

**综合实战**是将前序八个章节沉淀的 `skill/` 能力像搭积木一样组合起来，构建面向真实业务场景的完整 Agent 应用。本章不引入新的底层能力，而是聚焦**架构设计**、**接口契约**和**整合模式**。

核心原则：
- **零新能力**：所有功能必须来自 `01-foundation/` ~ `08-enterprise/` 的 `skill/`。
- **显式契约**：模块间的依赖关系、数据格式、错误处理必须在 README 中明文约定。
- **可替换性**：任何一个 skill/ 模块应能在不破坏整体架构的前提下被替换或升级。

## 项目结构

```
09-integration/
├── README.md
├── projects/
│   ├── customer_service/         # 智能客服
│   ├── data_analyst/             # 智能数据分析助手
│   └── ops_assistant/            # 运维助手
└── integration_patterns/         # 可复用的整合模式文档
    ├── pattern_rag_agent.md
    ├── pattern_multi_agent_workflow.md
    └── pattern_human_in_the_loop.md
```

## 搭积木指南

### 1. 智能客服（Customer Service）

| 积木 | 来源 | 用途 |
|------|------|------|
| `base_llm_client` | `01-foundation/skill/` | 统一 LLM 调用 |
| `tool_registry` | `02-tool-use/skill/` | 查询订单、创建工单、发送邮件 |
| `memory_store` | `03-memory/skill/` | 记住用户问题和上下文 |
| `reasoning_engine` | `04-reasoning/skill/` | ReAct 处理复杂售后流程 |
| `agent_loop` | `05-agent-core/skill/` | 主循环驱动 |
| `enterprise_guard` | `08-enterprise/skill/` | 权限校验、审计、敏感词过滤 |

**整合契约**：
- `agent_loop` 通过 `tool_registry` 发现工具，通过 `memory_store` 读写会话历史。
- `enterprise_guard` 包裹在 `agent_loop` 外层，对每次输入输出做过滤和审计。
- `reasoning_engine` 替换 `agent_loop` 中的默认思考逻辑。

### 2. 智能数据分析助手（Data Analyst）

| 积木 | 来源 | 用途 |
|------|------|------|
| `base_llm_client` | `01-foundation/skill/` | NL2SQL / 图表生成 |
| `tool_registry` | `02-tool-use/skill/` | 连接数据库、执行 SQL、生成图表 |
| `reasoning_engine` | `04-reasoning/skill/` | Plan-and-Solve 分解分析任务 |
| `workflow_engine` | `07-workflow/skill/` | 固化常见分析流程（如"日报生成"） |
| `enterprise_guard` | `08-enterprise/skill/` | SQL 注入检测、数据权限控制 |

**整合契约**：
- `workflow_engine` 负责高层流程（触发条件 -> 数据提取 -> 分析 -> 报告）。
- 每个流程节点内部使用 `agent_loop` + `reasoning_engine` 做灵活分析。
- 数据库工具必须通过 `enterprise_guard` 的权限校验后才能执行。

### 3. 运维助手（Ops Assistant）

| 积木 | 来源 | 用途 |
|------|------|------|
| `base_llm_client` | `01-foundation/skill/` | 日志解析、根因分析 |
| `tool_registry` | `02-tool-use/skill/` | 查询指标、重启服务、拉取日志 |
| `agent_loop` | `05-agent-core/skill/` | 排查循环 |
| `agent_swarm` | `06-multi-agent/skill/` | 网络专家 Agent + 应用专家 Agent 协作 |
| `enterprise_guard` | `08-enterprise/skill/` | 高危操作双重确认、全链路审计 |

**整合契约**：
- `agent_swarm` 采用层级模式：调度 Agent 分配子任务，专家 Agent 并行排查。
- 任何涉及变更的操作（如重启）必须通过 `enterprise_guard` 的人工确认节点。

## 企业应用注意点

1. **集成测试**：组合后的系统必须进行端到端集成测试，覆盖正常路径、异常路径和边界条件。单模块测试通过不等于组合后稳定。
2. **配置中心化**：多个 skill/ 模块的配置（模型选择、超时、权限规则）应集中管理，避免散落在各目录中。
3. **灰度发布**：新组合上线时，先对 5% 流量开放，观察错误率、延迟、成本后再全量。
4. **回滚策略**：每个 skill/ 模块升级前，保留旧版本接口兼容层，确保组合系统可快速回滚。
5. **文档同步**：任何 skill/ 接口变更必须同步更新 `09-integration/` 中的契约文档，否则整合层将逐渐腐化。

## 应用场景推演

### 场景：统一企业 Agent 平台
大型企业不满足于单点 Agent，希望构建平台：
1. **底座层**：复用 `01-foundation/skill/` ~ `08-enterprise/skill/` 作为平台 PaaS 能力。
2. **应用层**：各业务线基于 `09-integration/projects/` 模板快速搭建自己的 Agent（如 HR 助手、法务助手、IT 助手）。
3. **治理层**：通过 `enterprise_guard` 统一管控权限、审计和成本，防止各业务线重复造轮子且标准不一。

**注意点**：平台化意味着多租户、多版本、多模型共存，配置管理和依赖冲突将成为主要挑战。建议引入依赖注入容器管理 skill/ 生命周期。

## 学习终点与起点

完成本章后，你已经具备从单模块到企业级整合的完整视角。Agent 技术仍在快速演进，建议：
- 回归各章 `skill/`，检查接口是否依然简洁。
- 关注社区新范式（如 MCP、A2A 协议），评估是否值得引入为新章节。
- 在实际业务中验证，让真实用户反馈驱动迭代。
