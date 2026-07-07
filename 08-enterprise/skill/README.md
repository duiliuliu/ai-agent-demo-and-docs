# skill: enterprise_guard

## 设计目标

企业级横切能力的统一封装：身份权限、审计日志、输入输出过滤、RAG 接入。可被任何上层模块（agent_loop、workflow_engine）包裹使用。

## 接口清单

| 文件 | 职责 |
|------|------|
| `enterprise_guard.py` | 统一入口：权限检查、输入过滤、输出过滤、审计记录 |
| `iam_adapter.py` | 身份与权限适配器接口（可对接企业 IAM） |
| `audit_logger.py` | 结构化审计日志：记录谁、何时、做了什么、结果如何 |
| `guardrails.py` | 护栏规则引擎：敏感信息检测、注入攻击识别、输出合规检查 |
| `rag_pipeline.py` | RAG 流水线：文档加载、切分、嵌入、检索、重排序 |

## 使用方式

```python
from skill.enterprise_guard import EnterpriseGuard

guard = EnterpriseGuard(iam=iam_client, audit=audit_logger, rules=rules)
# 输入过滤
safe_input = guard.filter_input(user_input)
# 权限检查
if guard.check_permission(agent_id="ops_bot", resource="production_db", action="restart"):
    ...
# 输出过滤
safe_output = guard.filter_output(llm_response)
```

## 边界约束

- `enterprise_guard` 是横切层，不得侵入业务逻辑。
- 审计日志写入必须异步化，避免阻塞主流程。
- RAG 流水线应支持多种向量存储后端，禁止绑定单一闭源服务。
