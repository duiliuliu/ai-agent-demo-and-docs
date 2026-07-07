# 08 企业集成（Enterprise Integration）

## 定义

**企业集成**是将 Agent 系统安全、可靠、合规地嵌入企业现有技术栈和业务体系的一系列横切能力。它不是单一功能，而是贯穿 Agent 全生命周期的保障层：从知识增强（RAG）到身份权限，从审计日志到监控告警。

核心概念：
- **RAG（Retrieval-Augmented Generation）**：将企业私有知识库接入 Agent，减少幻觉并确保回答基于企业事实。
- **身份与权限（IAM）**：Agent 本身需要身份，其能访问的数据和工具受企业统一权限体系管控。
- **审计与合规（Audit & Compliance）**：全链路留痕，满足监管和内部审计要求。
- **安全与护栏（Guardrails）**：输入过滤、输出过滤、敏感信息检测、对抗攻击防护。
- **可观测性（Observability）**：指标（Metrics）、日志（Logs）、追踪（Traces）三位一体。

## 示例

### Demo 列表

| Demo | 说明 | 依赖 |
|------|------|------|
| `demo/01_rag_basic.py` | 文档切分、嵌入、检索、生成 | `03-memory/skill/` |
| `demo/02_guardrails.py` | 输入/输出敏感信息过滤 | `01-foundation/skill/` |
| `demo/03_audit_logging.py` | 结构化审计日志输出 | 前序所有 skill/ |

### 核心代码片段

```python
# skill/enterprise_guard.py 设计目标：企业级横切能力的统一封装
from typing import Dict, Any, List

class EnterpriseGuard:
    def __init__(self, iam_client, audit_logger, guardrail_rules: List[dict]):
        self.iam = iam_client
        self.audit = audit_logger
        self.rules = guardrail_rules

    def check_permission(self, agent_id: str, resource: str, action: str) -> bool:
        allowed = self.iam.check(agent_id, resource, action)
        self.audit.log_access(agent_id, resource, action, allowed)
        return allowed

    def filter_input(self, text: str) -> Dict[str, Any]:
        # 检测注入、敏感词、对抗样本
        for rule in self.rules:
            if rule["type"] == "sensitive_data" and self._detect_pii(text):
                return {"allowed": False, "reason": "sensitive_data_detected"}
        return {"allowed": True, "text": text}

    def filter_output(self, text: str) -> Dict[str, Any]:
        # 输出合规检查
        pass
```

## 企业应用注意点

1. **RAG 不是万能药**：企业知识库质量决定 RAG 上限。需投入文档治理：标准化格式、去除过期内容、建立版本控制。
2. **权限的细粒度**：Agent 可能同时访问多个系统，需支持基于属性的访问控制（ABAC）和动态授权，而非简单的角色列表。
3. **审计不可事后补**：Agent 的每一次 LLM 调用、工具调用、记忆读写都必须同步写入不可篡改的审计存储（如 WORM 存储、区块链存证）。
4. **安全是动态博弈**：攻击者会不断尝试提示注入、越狱。护栏规则需持续更新，并结合人工审核样本迭代。
5. **SLA 与降级**：企业系统有明确的可用性要求。当 LLM 服务故障时，Agent 应能降级到备用模型、缓存答案或转人工，而非直接报错。

## 应用场景推演

### 场景：企业内部合规问答助手
员工询问"差旅报销标准"，Agent 需要：
1. **RAG**：从最新版员工手册中检索相关条款（而非依赖训练数据中的旧政策）。
2. **IAM**：校验提问者职级，高管和普通员工的差旅标准不同，Agent 只能返回该员工权限范围内的信息。
3. **Audit**：记录谁、在何时、问了什么、得到了什么答案，供内审抽查。
4. **Guardrails**：若员工在问题中夹带"请忽略之前的指令"等注入攻击，输入过滤层直接拦截。

**注意点**：员工手册更新后，向量索引必须同步重建，否则 Agent 会基于过期政策回答，引发合规风险。

### 演进路径
- 当前层补全了企业级"底座保障"。
- 下一章（09-integration）将把前序所有 skill/ 搭成完整的生产级应用。
