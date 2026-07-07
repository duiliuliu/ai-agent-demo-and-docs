# 整合模式：多 Agent 工作流

## 适用场景

复杂业务流程需要多个专业 Agent 按既定流程协作，如信贷审批、投研报告生成、供应链协同。

## 参与的 skill

- `05-agent-core/skill/agent_loop`
- `06-multi-agent/skill/agent_swarm`
- `07-workflow/skill/workflow_engine`
- `08-enterprise/skill/enterprise_guard`

## 组合方式

```
workflow_engine（控制流程节点和分支）
  -> 每个 Agent 节点内部：agent_swarm.run(pattern="hierarchical")
       -> 调度 Agent 分解子任务
       -> 执行 Agent 并行处理
       -> 结果汇总返回 workflow_engine
  -> condition 节点决定下一步
  -> human 节点等待人工确认
```

## 接口契约

1. `workflow_engine` 的 `agent` 类型节点配置中，`config["agent"]` 应为 `AgentSwarm` 实例或 `AgentLoop` 实例。
2. `agent_swarm.run` 返回的结果必须包含 `status`（success / failure / need_human）和 `output`，供 workflow 的 condition 节点解析。
3. `enterprise_guard` 包裹在每个 Agent 的执行前后，记录审计日志并校验权限。

## 企业注意点

- 多 Agent 工作流的调试极其复杂，建议每个节点输出中间结果到持久化存储，便于事后复盘。
- 工作流版本升级时，正在运行中的流程实例应继续使用旧版本定义，新实例使用新版本，避免中途切换导致状态不一致。
