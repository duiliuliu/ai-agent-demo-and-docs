"""
Demo 02: 主子模式（层级调度协作）

场景：主 Agent 分解任务，调度子 Agent 执行，汇总结果
协作模式：HIERARCHICAL
通信方式：集中式（Centralized）

适用场景：
  - 复杂任务需要统筹协调
  - 报告生成（调研+分析+撰写+审查）
  - 项目分解执行

运行方式：
  python demo/02_hierarchical.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.demo_helper import create_mock_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern


def demo_hierarchical():
    """主子模式演示"""
    print_config_info()
    
    # 创建协作系统（集中式通信）
    swarm = AgentSwarm(
        name="report_team",
        max_rounds=10,
        communication_mode="centralized"
    )
    
    # 注册主 Agent（调度员）
    swarm.register(
        name="主编调度员",
        agent_instance=create_mock_agent("主编调度员", "调度员",
            "作为主编，我将任务分解为：1.数据收集 -> 数据员 2.分析 -> 分析师 3.撰写 -> 撰写员"),
        role="调度员",
        capabilities=["任务分解", "结果汇总", "质量把控"],
        is_coordinator=True  # 标记为主调度员
    )
    
    # 注册子 Agent（执行者）
    swarm.register(
        name="数据员",
        agent_instance=create_mock_agent("数据员", "数据收集",
            "[数据员] 收集数据完成：市场报告、竞品分析、用户调研数据"),
        role="数据收集",
        capabilities=["数据抓取", "信息检索"]
    )
    
    swarm.register(
        name="分析师",
        agent_instance=create_mock_agent("分析师", "数据分析",
            "[分析师] 基于数据员提供的数据，分析结论：市场增长率15%，竞品优势明显"),
        role="数据分析",
        capabilities=["数据处理", "统计分析"]
    )
    
    swarm.register(
        name="撰写员",
        agent_instance=create_mock_agent("撰写员", "文档撰写",
            "[撰写员] 整合分析结果，撰写报告：第一章市场概况，第二章竞品对比..."),
        role="文档撰写",
        capabilities=["文案写作", "报告生成"]
    )
    
    swarm.register(
        name="审查员",
        agent_instance=create_mock_agent("审查员", "内容审查",
            "[审查员] 审查结果：数据准确，分析合理，文案符合规范，建议发布"),
        role="内容审查",
        capabilities=["质量检查", "合规审查"]
    )
    
    # 定义复杂任务
    task = "生成一份AI行业市场分析报告"
    
    print(f"任务: {task}")
    print(f"主Agent: 主编调度员")
    print(f"子Agent: 数据员、分析师、撰写员、审查员")
    print(f"协作模式: 主子模式（Hierarchical）")
    print()
    
    # 执行协作
    result = swarm.run(
        task=task,
        pattern=CollaborationPattern.HIERARCHICAL
    )
    
    print_result(result, "报告生成结果")
    
    # 分析执行流程
    print("=" * 60)
    print("执行流程分析")
    print("=" * 60)
    print("""
预期流程：
  1. 主编调度员分解任务 → 分配给各子Agent
  2. 数据员执行数据收集 → 返回数据结果
  3. 分析师基于数据进行分析 → 返回分析结论
  4. 撰写员整合数据和分析 → 生成报告草稿
  5. 审查员检查报告质量 → 返回审查意见
  6. 主编调度员汇总所有结果 → 输出最终报告
""")
    
    return result


def explain_hierarchical():
    """解释主子模式"""
    print("=" * 60)
    print("主子模式（Hierarchical）解析")
    print("=" * 60)
    print("""
## 协作流程

1. 主 Agent（调度员）接收任务
2. 主 Agent 分解任务为子任务
3. 主 Agent 分配子任务给子 Agent
4. 子 Agent 执行子任务，返回结果
5. 主 Agent 汇总结果，输出最终答案

## 关键设计点

1. **任务分解能力**：主 Agent 需要理解任务，合理分解
2. **任务分配匹配**：根据子 Agent 能力分配任务
3. **结果汇总逻辑**：主 Agent 整合多子 Agent 的结果
4. **错误处理**：子 Agent 失败时，主 Agent 需要重试或降级

## 与平等协作的区别

| 维度 | 平等协作 | 主子模式 |
|------|----------|----------|
| 角色 | 平等地位 | 主从关系 |
| 通信 | 点对点 | 集中式 |
| 决策 | 共识达成 | 主Agent裁决 |
| 效率 | 可能讨论轮次多 | 一次执行即可 |

## 适用场景

- 报告生成：调研→分析→撰写→审查
- 项目执行：分解→分配→执行→汇总
- 复杂任务：需要统筹协调的情况

## 企业注意点

1. **调度员瓶颈**：主 Agent 负载可能过重，需要缓冲机制
2. **子 Agent 并发**：可以并行执行无依赖的子任务
3. **结果一致性**：多个子 Agent 结果可能矛盾，需要仲裁
4. **身份权限**：子 Agent 不应越权调用其他 Agent
""")


if __name__ == "__main__":
    demo_hierarchical()
    explain_hierarchical()