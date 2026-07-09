"""
Demo 05: 可观测性与监控

场景：展示 Agent 的可观测性能力（生命周期钩子、指标、追踪、审计）
目标：理解企业级 Agent 系统的监控和稳定性保障机制

核心知识点：
  1. 生命周期钩子（Hooks）：before_step / after_step / on_error 等
  2. 指标采集（Metrics）：步数、耗时、Token 消耗、成功率等
  3. 全链路追踪（Tracing）：每步的详细信息和时间线
  4. 审计日志（Audit Log）：合规性和可追溯性

支持真实 LLM：
  支持所有 LLM 提供商 + 所有推理类型
    export LLM_PROVIDER=openai
    export LLM_API_KEY=your-api-key
    export REASONING_TYPE=react

运行方式：
  python demo/05_observability.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_helper import create_agent_loop, print_config_info


class ObservabilityHook:
    def __init__(self):
        self.step_count = 0
        self.total_duration = 0
        self.errors = []
        self.events = []

    def on_step_start(self, step_id):
        self.step_count += 1
        self.events.append({
            "type": "step_start",
            "step_id": step_id,
            "timestamp": self._timestamp()
        })
        print(f"  [Hook] 步骤 {step_id} 开始")

    def on_step_end(self, step):
        action_type = step.action.type.value if step.action else "none"
        self.events.append({
            "type": "step_end",
            "step_id": step.step_id,
            "action_type": action_type,
            "timestamp": self._timestamp()
        })
        print(f"  [Hook] 步骤 {step.step_id} 完成，动作: {action_type}")

    def on_loop_start(self, session_id, user_input):
        self.events.append({
            "type": "loop_start",
            "session_id": session_id,
            "timestamp": self._timestamp()
        })
        print(f"  [Hook] 循环开始，会话ID: {session_id}")

    def on_loop_end(self, session_id, status):
        self.events.append({
            "type": "loop_end",
            "session_id": session_id,
            "status": status,
            "timestamp": self._timestamp()
        })
        print(f"  [Hook] 循环结束，状态: {status}")

    def _timestamp(self):
        import time
        return time.time()


def demo_lifecycle_hooks():
    print("\n" + "=" * 60)
    print("场景 1: 生命周期钩子")
    print("=" * 60)

    hook = ObservabilityHook()

    loop = create_agent_loop(
        max_steps=3,
        on_step_start=hook.on_step_start,
        on_step_end=hook.on_step_end,
        on_loop_start=hook.on_loop_start,
        on_loop_end=hook.on_loop_end
    )

    user_input = "分析一下人工智能的发展趋势"

    print(f"\n用户输入: {user_input}\n")

    result = loop.run(user_input)

    print(f"\n钩子统计:")
    print(f"  执行步数: {hook.step_count}")
    print(f"  事件总数: {len(hook.events)}")
    print(f"  错误数量: {len(hook.errors)}")
    print()


def demo_metrics():
    print("=" * 60)
    print("场景 2: 指标采集")
    print("=" * 60)

    loop = create_agent_loop(max_steps=4)

    user_input = "帮我规划一次周末旅行"

    result = loop.run(user_input)

    print("  核心指标:")
    print(f"    总步数: {len(result.steps)}")
    print(f"    总耗时: {result.total_duration_ms / 1000:.3f}秒")
    print(f"    是否成功: {result.status.value == 'completed'}")
    print(f"    终止原因: {result.status.value}")
    print()

    if hasattr(result, 'metrics') and result.metrics:
        print("  详细指标:")
        for key, value in result.metrics.items():
            print(f"    {key}: {value}")
        print()

    print("  企业级指标建议:")
    print("    - 成功率: 成功任务 / 总任务数")
    print("    - 平均耗时: 总耗时 / 任务数")
    print("    - Token 消耗: 输入/输出 Token 统计")
    print("    - 成本: 按 Token 单价计算的费用")
    print("    - 工具调用次数: 平均每次任务的工具调用数")
    print("    - 错误率: 错误任务 / 总任务数")
    print("    - 用户满意度: 人工评分或反馈")
    print()


def demo_tracing():
    print("=" * 60)
    print("场景 3: 全链路追踪")
    print("=" * 60)

    loop = create_agent_loop(max_steps=3)

    user_input = "介绍一下机器学习的基本概念"

    result = loop.run(user_input)

    print("  步骤详情:")
    for i, step in enumerate(result.steps, 1):
        print(f"\n  Step {i}:")
        print(f"    思考: {step.thought[:60]}...")
        if step.action:
            print(f"    动作: {step.action.type.value} - {step.action.name}")
            print(f"    参数: {json.dumps(step.action.args, ensure_ascii=False)[:60]}...")
        if step.result:
            print(f"    结果: {str(step.result)[:60]}...")
    print()

    print("  追踪能力的价值:")
    print("    - 调试问题：快速定位失败步骤")
    print("    - 性能分析：找出耗时瓶颈")
    print("    - 质量评估：评估推理质量")
    print("    - 安全审计：追溯每一步操作")
    print("    - 优化迭代：基于数据改进 Agent")
    print()


def demo_audit_log():
    print("=" * 60)
    print("场景 4: 审计日志")
    print("=" * 60)

    print("  审计日志的重要性:")
    print("    - 合规要求：满足金融、医疗等行业监管")
    print("    - 责任追溯：谁在什么时间做了什么操作")
    print("    - 安全防护：检测异常行为和安全威胁")
    print("    - 质量保证：审核 Agent 的决策过程")
    print()

    print("  审计日志应包含:")
    print("    - 时间戳：精确到毫秒的操作时间")
    print("    - 用户标识：发起请求的用户/系统")
    print("    - 请求内容：用户的原始输入")
    print("    - 决策过程：Agent 的思考和推理链")
    print("    - 执行动作：具体的操作和参数")
    print("    - 返回结果：最终的输出内容")
    print("    - 资源消耗：Token、计算资源等")
    print()

    print("  存储建议:")
    print("    - 不可篡改：使用追加写、WORM 存储")
    print("    - 长期保存：根据合规要求设定保留期限")
    print("    - 加密存储：敏感信息加密")
    print("    - 可检索：支持按时间、用户、类型检索")
    print()


def demo_enterprise_best_practices():
    print("=" * 60)
    print("企业级稳定性最佳实践")
    print("=" * 60)
    print("""
1. 异常隔离（Fault Isolation）：
   - 单步失败不影响整体流程
   - 重试机制：临时性错误自动重试
   - 降级策略：核心功能优先保证

2. 资源限额（Resource Quotas）：
   - 每用户每天 Token 限额
   - 每任务最大步数限制
   - 并发数限制
   - 队列长度限制

3. 优雅降级（Graceful Degradation）：
   - LLM 不可用时使用降级方案
   - 工具失败时提供备选方案
   - 超时保护和快速失败

4. 监控告警（Monitoring & Alerting）：
   - 关键指标实时监控
   - 异常检测和自动告警
   - 仪表盘可视化
   - SLA 承诺和保障

5. 灰度发布（Canary Release）：
   - 新版本小流量验证
   - A/B 测试对比效果
   - 快速回滚能力

6. 版本管理（Versioning）：
   - Agent 版本化
   - Prompt 版本化
   - 工具版本化
   - 配置版本化

使用真实 LLM 体验：
  # 完整可观测性演示
  export LLM_PROVIDER=openai
  export LLM_API_KEY=your-api-key
  export REASONING_TYPE=react
  python demo/05_observability.py
""")


if __name__ == "__main__":
    print_config_info()
    demo_lifecycle_hooks()
    demo_metrics()
    demo_tracing()
    demo_audit_log()
    demo_enterprise_best_practices()
