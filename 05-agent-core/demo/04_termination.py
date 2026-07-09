"""
Demo 04: 多种终止条件处理

场景：展示 Agent 循环的各种终止条件和处理方式
目标：理解不同终止条件的触发机制和处理策略

核心知识点：
  1. 终止条件的类型和配置
  2. 如何监控循环状态
  3. 终止原因的判断和处理
  4. 资源限额和成本控制

运行方式：
  python demo/04_termination.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill.termination_checker import (
    TerminationChecker,
    SmartTerminationChecker,
    TerminationConfig,
    TerminationReason
)


def demo_termination_conditions():
    print("=" * 60)
    print("Demo 04: 多种终止条件处理")
    print("=" * 60)
    print()

    print("=" * 60)
    print("测试1：标准终止检查器")
    print("=" * 60)

    config = TerminationConfig(
        max_steps=3,
        max_time_seconds=10,
        max_llm_calls=5,
        max_tool_calls=3,
        max_consecutive_failures=2
    )

    checker = TerminationChecker(config)
    checker.initialize()

    test_cases = [
        {"success": True, "llm_calls": 1, "tool_calls": 0},
        {"success": True, "llm_calls": 1, "tool_calls": 0},
        {"success": True, "llm_calls": 1, "tool_calls": 0},
    ]

    for i, step in enumerate(test_cases, 1):
        reason = checker.check(step)
        state = checker.get_state()
        print(f"步骤 {i}: 终止原因={reason.value}, 状态={state}")

    print()

    print("=" * 60)
    print("测试2：连续失败触发终止")
    print("=" * 60)

    checker2 = TerminationChecker(config)
    checker2.initialize()

    failure_cases = [
        {"success": False, "llm_calls": 1, "tool_calls": 0},
        {"success": False, "llm_calls": 1, "tool_calls": 0},
        {"success": False, "llm_calls": 1, "tool_calls": 0},
    ]

    for i, step in enumerate(failure_cases, 1):
        reason = checker2.check(step)
        state = checker2.get_state()
        print(f"步骤 {i}: 终止原因={reason.value}, 连续失败={state['consecutive_failures']}")

    print()

    print("=" * 60)
    print("测试3：智能终止检查器（进度趋势检测）")
    print("=" * 60)

    smart_checker = SmartTerminationChecker(config)
    smart_checker.initialize()

    trend_cases = [
        {"success": True, "progress": 0, "new_information": False},
        {"success": True, "progress": 0, "new_information": False},
        {"success": True, "progress": 0, "new_information": False},
        {"success": True, "progress": 0, "new_information": False},
        {"success": True, "progress": 0, "new_information": False},
    ]

    for i, step in enumerate(trend_cases, 1):
        reason = smart_checker.check(step)
        print(f"步骤 {i}: 终止原因={reason.value}, 进度={step['progress']}")

    print()

    print("=" * 60)
    print("测试4：终止消息和正常终止判断")
    print("=" * 60)

    reasons = [
        TerminationReason.TASK_COMPLETED,
        TerminationReason.MAX_STEPS_REACHED,
        TerminationReason.TIME_LIMIT_EXCEEDED,
        TerminationReason.USER_INTERRUPTED,
        TerminationReason.FATAL_ERROR,
        TerminationReason.QUALITY_THRESHOLD,
        TerminationReason.COST_LIMIT_EXCEEDED,
    ]

    for reason in reasons:
        msg = checker.get_termination_message(reason)
        is_normal = checker.is_normal_termination(reason)
        print(f"{reason.value}: {msg} (正常终止={is_normal})")

    print()

    print("=" * 60)
    print("终止条件机制解析")
    print("=" * 60)
    print("""
1. 终止条件类型：
   - TASK_COMPLETED: 任务完成（推理引擎返回完成信号）
   - MAX_STEPS_REACHED: 达到最大步数限制
   - TIME_LIMIT_EXCEEDED: 超过时间限制
   - USER_INTERRUPTED: 用户主动中断
   - FATAL_ERROR: 发生致命错误
   - QUALITY_THRESHOLD: 质量阈值（连续失败或低置信度）
   - COST_LIMIT_EXCEEDED: 成本或调用次数超限

2. 配置参数：
   - max_steps: 最大循环步数
   - max_time_seconds: 最大运行时间（秒）
   - max_llm_calls: 最大LLM调用次数
   - max_tool_calls: 最大工具调用次数
   - max_consecutive_failures: 最大连续失败次数
   - max_total_cost: 最大成本限制
   - min_confidence_threshold: 最小置信度阈值

3. 智能终止检测（SmartTerminationChecker）：
   - 检测连续失败趋势
   - 检测无进展循环（重复相同操作）
   - 提前终止低效循环，节省资源

4. 正常终止 vs 异常终止：
   - 正常终止：任务完成、步数上限、时间上限、用户中断
   - 异常终止：致命错误、质量阈值、成本超限

5. 实际应用建议：
   - 根据场景调整配置（简单任务：少步数，复杂任务：多步数）
   - 监控终止原因分布，优化配置
   - 对异常终止进行告警和复盘
   - 设置合理的资源限额，防止滥用

关键设计原则：
  - 终止条件应该是可配置的（适应不同场景）
  - 终止原因应该是可追踪的（便于分析和优化）
  - 资源限额应该是可监控的（便于成本控制）
  - 终止应该是优雅的（保留已执行步骤的结果）
""")


if __name__ == "__main__":
    demo_termination_conditions()
