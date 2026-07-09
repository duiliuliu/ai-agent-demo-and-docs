"""
Demo 04: 多种终止条件处理

场景：展示 Agent 循环的多种终止条件（步数、时间、质量、成本）
目标：理解如何控制 Agent 循环的资源限额和智能终止

核心知识点：
  1. 基于步数的终止条件
  2. 基于时间的终止条件
  3. 基于成本的终止条件
  4. 基于质量的终止条件
  5. 智能趋势分析和提前终止

支持真实 LLM：
  支持所有 LLM 提供商
    export LLM_PROVIDER=deepseek
    export LLM_API_KEY=your-api-key
    export REASONING_TYPE=simple

运行方式：
  python demo/04_termination.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_helper import create_agent_loop, print_config_info


def demo_step_termination():
    print("\n" + "=" * 60)
    print("场景 1: 基于步数的终止条件")
    print("=" * 60)

    loop = create_agent_loop(max_steps=3)

    user_input = "详细分析如何学习 Python 编程的核心概念"

    result = loop.run(user_input)

    print(f"  终止原因: {result.status.value}")
    print(f"  执行步数: {len(result.steps)}")
    print(f"  是否成功: {result.status.value == 'completed'}")
    print()


def demo_time_termination():
    print("=" * 60)
    print("场景 2: 基于时间的终止条件")
    print("=" * 60)

    loop = create_agent_loop(
        max_steps=10,
        max_total_time_seconds=2
    )

    user_input = "请用很多步骤分析一个复杂的问题"

    result = loop.run(user_input)

    print(f"  终止原因: {result.status.value}")
    print(f"  执行步数: {len(result.steps)}")
    print(f"  执行时间: {result.total_duration_ms / 1000:.2f}秒")
    print()


def demo_quality_termination():
    print("=" * 60)
    print("场景 3: 基于质量的终止条件")
    print("=" * 60)

    from skill.termination_checker import TerminationChecker, TerminationConfig

    config = TerminationConfig(
        max_steps=10,
        min_confidence_threshold=0.8
    )
    checker = TerminationChecker(config=config)

    print("  质量阈值: 当检测到高置信度回答时提前终止")
    print("  适用场景: 推理结果置信度达到要求后无需继续迭代")
    print()
    print("  终止检查维度:")
    print("    - 步数限制: 防止无限循环")
    print("    - 时间限制: 防止执行时间过长")
    print("    - LLM调用次数: 控制调用成本")
    print("    - 工具调用次数: 防止过度使用工具")
    print("    - 连续失败: 检测卡壳状态")
    print("    - 成本限制: 控制总体成本")
    print("    - 置信度阈值: 结果质量达标后提前终止")
    print()


def demo_trend_analysis():
    print("=" * 60)
    print("场景 4: 智能趋势分析")
    print("=" * 60)

    print("  趋势分析的目的:")
    print("    当连续多步没有实质进展时，智能终止循环")
    print()
    print("  常见无进展的表现:")
    print("    - 重复相同的思考和行动")
    print("    - 工具调用没有新信息")
    print("    - 在原地打转，无法推进任务")
    print()
    print("  企业级应用价值:")
    print("    - 防止死循环，节省 LLM 调用成本")
    print("    - 及时发现卡壳，避免资源浪费")
    print("    - 提升用户体验，快速返回结果")
    print()


def demo_termination_summary():
    print("=" * 60)
    print("终止条件总结")
    print("=" * 60)
    print("""
1. 最大步数限制（Max Steps）：
   - 最基本的保护机制
   - 防止无限循环
   - 默认值通常根据任务复杂度设置

2. 超时限制（Timeout）：
   - 防止任务执行时间过长
   - 特别适用于有 SLA 要求的场景
   - 结合异步任务调度

3. 成本控制（Cost Limit）：
   - 控制 LLM 调用的 Token 成本
   - 企业级预算管理
   - 按用户/部门/项目级别的配额

4. 质量阈值（Quality Threshold）：
   - 结果达到质量要求后提前终止
   - 避免不必要的迭代
   - 提升效率，降低成本

5. 智能趋势分析（Trend Analysis）：
   - 检测无进展循环
   - 防止死循环
   - 及时止损

企业级实践建议：
  - 多种终止条件组合使用
  - 为不同场景配置不同的阈值
  - 记录终止原因用于分析和优化
  - 设置合理的默认值，防止误触发
  - 提供配置化管理终止策略

使用真实 LLM 体验：
  # 使用 DeepSeek + Plan-and-Solve 模式
  export LLM_PROVIDER=deepseek
  export LLM_API_KEY=your-api-key
  export REASONING_TYPE=plan
  python demo/04_termination.py
""")


if __name__ == "__main__":
    print_config_info()
    demo_step_termination()
    demo_time_termination()
    demo_quality_termination()
    demo_trend_analysis()
    demo_termination_summary()
