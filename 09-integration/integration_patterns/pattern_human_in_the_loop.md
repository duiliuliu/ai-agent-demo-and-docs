# 整合模式：Human-in-the-Loop

## 适用场景

高风险决策、关键审批、AI 置信度不足时需要人工介入的场景，如财务审批、医疗诊断辅助、安全事件响应。

## 参与的 skill

- `05-agent-core/skill/agent_loop`
- `07-workflow/skill/workflow_engine`
- `08-enterprise/skill/enterprise_guard`

## 组合方式

```
agent_loop 执行自动分析
  -> workflow_engine 遇到 "human" 类型节点
       -> 暂停流程，持久化当前状态
       -> 通过企业 IM / 邮件 / 工单系统通知审批人
       -> 等待审批人输入（同意 / 拒绝 / 补充信息）
       -> 恢复流程，将人工决策注入上下文
  -> agent_loop 继续后续步骤或终止
```

## 接口契约

1. `workflow_engine` 的 `human` 节点必须支持 `suspend()` 和 `resume(human_input: dict)` 两种状态转换。
2. 人工输入必须通过 `enterprise_guard.filter_input` 校验，防止审批人被社工攻击后输入恶意指令。
3. 暂停期间，流程上下文必须持久化到数据库，支持服务重启后恢复。

## 企业注意点

- 人工节点必须设置 SLA 和升级机制：如 24 小时未响应，自动升级给上级或转人工客服。
- 审批人的操作记录（同意/拒绝/修改意见）必须完整记入审计日志，满足合规要求。
- 对频繁触发人工介入的流程，应回溯分析 Agent 的置信度或推理策略，持续优化自动通过率。
