"""
Demo 07: 企业级多 Agent 系统（深度工程化）

展示以下企业级特性：
1. 共享黑板：持久化 + 乐观锁 + 分布式锁 + CAS
2. 异步广播：非阻塞发送 + 回调 + 超时控制
3. 快速通道：阻塞/非阻塞 + 批量接收 + 条件过滤
4. 容错机制：心跳检测 + 熔断器 + 故障转移 + 重试

运行方式：
  python demo/07_enterprise_demo.py
"""
import os
import sys
import time
import threading

demo_dir = os.path.dirname(os.path.abspath(__file__))
module_dir = os.path.dirname(demo_dir)
sys.path.insert(0, module_dir)

from skill.communication_bus import BlackboardBus, AsyncBroadcastBus, FastChannelBus
from skill.agent_monitor import (
    HeartbeatMonitor, RetryPolicy, CircuitBreaker,
    FailoverManager, ResilientAgentSwarm, AgentStatus
)


def demo_blackboard_advanced():
    """演示增强版共享黑板"""
    print("=" * 60)
    print("Demo 1: 共享黑板（持久化 + 一致性 + 锁）")
    print("=" * 60)

    # 创建带持久化的黑板
    blackboard = BlackboardBus(
        persistent_file="/tmp/blackboard_demo.json",
        max_history=100
    )

    # 场景1：正常写入和读取
    print("\n[场景1] 正常写入和读取")
    success, msg = blackboard.write("report_data", "初始报告数据", agent="Agent_A", trace_id="task_001")
    print(f"  Agent_A 写入: {msg}")

    value, version, msg = blackboard.read("report_data", agent="Agent_B")
    print(f"  Agent_B 读取: {msg}, 值={value}, 版本={version}")

    # 场景2：乐观锁冲突
    print("\n[场景2] 乐观锁冲突检测")
    success, msg = blackboard.write("report_data", "更新后的数据", agent="Agent_C",
                                     trace_id="task_002", use_optimistic_lock=True, expected_version=1)
    print(f"  Agent_C 写入(期望版本1): {msg}")

    success, msg = blackboard.write("report_data", "错误的数据", agent="Agent_D",
                                     trace_id="task_003", use_optimistic_lock=True, expected_version=1)
    print(f"  Agent_D 写入(期望版本1): {msg}")

    # 场景3：CAS 操作
    print("\n[场景3] CAS（Compare And Swap）原子操作")
    success, msg = blackboard.compare_and_swap("report_data", "更新后的数据", "CAS更新数据",
                                                agent="Agent_E", trace_id="task_004")
    print(f"  Agent_E CAS: {msg}")

    success, msg = blackboard.compare_and_swap("report_data", "错误值", "不应写入",
                                                agent="Agent_F", trace_id="task_005")
    print(f"  Agent_F CAS: {msg}")

    # 场景4：锁状态和历史
    print("\n[场景4] 锁状态和变更历史")
    lock_status = blackboard.get_lock_status("report_data")
    print(f"  锁状态: {lock_status}")

    history = blackboard.get_history("report_data")
    print(f"  变更历史条数: {len(history)}")
    for h in history[-3:]:
        print(f"    [{h['agent']}] v{h['version']}: {h['old_value']} -> {h['new_value']}")

    # 清理持久化文件
    if os.path.exists("/tmp/blackboard_demo.json"):
        os.remove("/tmp/blackboard_demo.json")


def demo_async_broadcast():
    """演示异步广播"""
    print("\n" + "=" * 60)
    print("Demo 2: 异步广播（非阻塞 + 回调 + 超时）")
    print("=" * 60)

    async_bus = AsyncBroadcastBus(max_workers=5, default_timeout=5.0)

    print("\n[场景1] 异步广播消息")
    task_id = async_bus.broadcast_async(
        sender="调度员",
        receivers=["Agent_1", "Agent_2", "Agent_3"],
        content="执行数据分析任务",
        trace_id="broadcast_001",
        callback=lambda result: print(f"  [回调] 广播完成: {result}")
    )
    print(f"  任务已提交，ID: {task_id}")

    # 等待结果
    print("  等待结果...")
    result = async_bus.wait_for_result(task_id, timeout=3.0)
    print(f"  结果: {result}")

    # 场景2：批量异步任务
    print("\n[场景2] 批量异步任务")
    task_ids = []
    for i in range(3):
        tid = async_bus.broadcast_async(
            sender="调度员",
            receivers=[f"Agent_{i}"],
            content=f"子任务 {i}",
            trace_id=f"batch_{i}"
        )
        task_ids.append(tid)
        print(f"  提交任务 {i}, ID: {tid}")

    print(f"  待处理任务数: {len(async_bus.get_pending_tasks())}")

    # 等待所有任务
    for tid in task_ids:
        async_bus.wait_for_result(tid, timeout=2.0)

    async_bus.shutdown()
    print("  所有异步任务完成")


def demo_fast_channel():
    """演示快速通道"""
    print("\n" + "=" * 60)
    print("Demo 3: 快速通道（阻塞/非阻塞 + 批量 + 过滤）")
    print("=" * 60)

    fast_bus = FastChannelBus()

    # 注册通道
    fast_bus.register_channel("Agent_X", maxsize=10)
    fast_bus.register_channel("Agent_Y", maxsize=10)

    print("\n[场景1] 非阻塞发送和接收")
    fast_bus.send_fast("Agent_X", "Agent_Y", "紧急消息1", blocking=False)
    fast_bus.send_fast("Agent_X", "Agent_Y", "普通消息", blocking=False)
    fast_bus.send_fast("Agent_X", "Agent_Y", "紧急消息2", blocking=False)

    msg = fast_bus.receive_non_blocking("Agent_Y")
    print(f"  非阻塞接收: {msg.content if msg else 'None'}")

    print("\n[场景2] 条件过滤接收（只接收紧急消息）")
    is_urgent = lambda m: "紧急" in str(m.content)
    msg = fast_bus.receive_non_blocking("Agent_Y", predicate=is_urgent)
    print(f"  过滤接收(紧急): {msg.content if msg else 'None'}")

    print("\n[场景3] 批量接收")
    # 发送多条消息
    for i in range(5):
        fast_bus.send_fast("Agent_X", "Agent_Y", f"批量消息{i}", blocking=False)

    messages = fast_bus.receive_batch("Agent_Y", max_messages=3, timeout=0.5)
    print(f"  批量接收 {len(messages)} 条消息")
    for m in messages:
        print(f"    - {m.content}")

    print("\n[场景4] 阻塞接收（模拟Agent等待消息）")
    def sender_thread():
        time.sleep(0.5)
        fast_bus.send_fast("Agent_X", "Agent_Y", "延迟消息", blocking=False)
        print("  [发送线程] 消息已发送")

    t = threading.Thread(target=sender_thread)
    t.start()

    print("  [接收线程] 等待消息...")
    msg = fast_bus.receive_blocking("Agent_Y", timeout=2.0)
    print(f"  [接收线程] 收到: {msg.content if msg else '超时'}")
    t.join()

    # 通道统计
    stats = fast_bus.get_channel_stats("Agent_Y")
    print(f"\n[通道统计] Agent_Y: {stats}")


def demo_resilient_system():
    """演示容错系统"""
    print("\n" + "=" * 60)
    print("Demo 4: 容错系统（心跳 + 熔断 + 故障转移）")
    print("=" * 60)

    resilient = ResilientAgentSwarm(name="production_swarm")

    # 注册 Agent（带故障转移链）
    def create_agent(name, fail_prob=0.0):
        """创建模拟 Agent，有概率失败"""
        def agent_func(prompt):
            import random
            if random.random() < fail_prob:
                raise Exception(f"{name} 模拟故障")
            return f"[{name}] 处理成功: {prompt[:20]}"
        return agent_func

    resilient.register_agent("主Agent", create_agent("主Agent", fail_prob=0.0))
    resilient.register_agent("备用Agent_A", create_agent("备用A", fail_prob=0.0))
    resilient.register_agent("备用Agent_B", create_agent("备用B", fail_prob=0.3))

    # 注册故障转移链
    resilient.failover_manager.register_failover("主Agent", ["备用Agent_A", "备用Agent_B"])

    # 场景1：正常调用
    print("\n[场景1] 正常调用")
    success, result, details = resilient.call_agent_resilient("主Agent", "执行任务1")
    print(f"  结果: {'成功' if success else '失败'}, {details}")
    print(f"  输出: {result}")

    # 场景2：模拟 Agent 心跳超时
    print("\n[场景2] 心跳超时检测")
    resilient.heartbeat_monitor.agents["主Agent"].last_heartbeat = time.time() - 100
    resilient.heartbeat_monitor._check_all_agents()
    health = resilient.heartbeat_monitor.get_health("主Agent")
    print(f"  主Agent 状态: {health.status.value}")

    # 场景3：故障转移
    print("\n[场景3] 故障转移")
    success, result, details = resilient.call_agent_resilient("主Agent", "执行任务2")
    print(f"  结果: {'成功' if success else '失败'}, {details}")
    print(f"  输出: {result}")

    # 场景4：熔断器
    print("\n[场景4] 熔断器测试")
    # 创建一个总是失败的 Agent
    resilient.register_agent("脆弱Agent", create_agent("脆弱Agent", fail_prob=1.0))

    for i in range(7):
        success, result, details = resilient.call_agent_resilient("脆弱Agent", f"任务{i}")
        circuit_stats = resilient.circuit_breaker.get_stats("脆弱Agent")
        print(f"  调用 {i+1}: {'成功' if success else '失败'}, "
              f"熔断状态: {circuit_stats['state']}, "
              f"失败计数: {circuit_stats['failure_count']}")

    # 检查最终状态
    print("\n[系统健康状态]")
    health_data = resilient.get_system_health()
    for name, data in health_data.items():
        print(f"  {name}:")
        print(f"    健康: {data['health'].get('status', 'unknown')}")
        print(f"    熔断: {data['circuit']['state']}")
        print(f"    失败: {data['circuit']['failure_count']}")


def explain_enterprise_design():
    """解释企业级设计"""
    print("\n" + "=" * 60)
    print("企业级多 Agent 系统设计要点")
    print("=" * 60)
    print("""
## 1. 共享黑板的一致性保障

### 问题：多个 Agent 同时写入同一数据，如何保障一致性？

解决方案：
- **分布式锁**：写入前获取锁，防止并发写入冲突
- **乐观锁**：版本控制，写入时检查版本号，冲突时拒绝
- **CAS 操作**：原子性 Compare-And-Swap，确保数据一致性
- **持久化**：定期序列化到磁盘，防止数据丢失

## 2. 异步广播的效率优化

### 问题：广播消息给多个 Agent，等待所有响应太慢？

解决方案：
- **非阻塞发送**：提交任务后立即返回，不等待
- **线程池**：使用线程池并行处理多个接收者
- **回调机制**：完成后通过回调通知调用方
- **超时控制**：设置超时时间，避免无限等待

## 3. 快速通道的灵活通信

### 问题：Agent 有的需要阻塞等待，有的需要轮询检查？

解决方案：
- **阻塞接收**：使用 Condition.wait()，有消息时唤醒
- **非阻塞接收**：立即返回，无消息返回 None
- **条件过滤**：只接收符合特定条件的消息
- **批量接收**：一次接收多条，减少系统调用

## 4. Agent 容错的完整方案

### 问题：Agent 死机了怎么办？

解决方案：
- **心跳检测**：定期检查 Agent 是否存活
- **超时重试**：调用失败时自动重试（指数退避）
- **熔断机制**：连续失败时快速失败，防止雪崩
- **故障转移**：主 Agent 失败时切换到备用
- **服务降级**：资源不足时降低服务质量

## 5. 工程实践建议

1. **监控优先**：所有 Agent 必须有健康监控
2. **快速失败**：熔断器避免级联故障
3. **优雅降级**：核心功能优先保障
4. **数据一致性**：共享状态必须有锁保护
5. **通信隔离**：不同通信模式适用于不同场景
""")


if __name__ == "__main__":
    demo_blackboard_advanced()
    demo_async_broadcast()
    demo_fast_channel()
    demo_resilient_system()
    explain_enterprise_design()