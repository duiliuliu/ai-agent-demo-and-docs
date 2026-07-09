"""
Demo 05: 竞争模式（Competition Collaboration）

场景：多个 Agent 竞争完成同一任务，选出最优结果
协作模式：COMPETITION
通信方式：集中式（Centralized）

适用场景：
  - 方案设计：多个方案对比选优
  - 创意生成：收集多样化创意
  - 模型对比：不同模型结果对比

运行方式：
  python demo/05_competition.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.demo_helper import create_mock_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern


def demo_competition():
    """竞争模式演示"""
    print_config_info()
    
    # 创建竞争协作系统
    swarm = AgentSwarm(
        name="competition_team",
        max_rounds=10,
        communication_mode="centralized"
    )
    
    # 注册多个竞争 Agent（优先级不同）
    swarm.register(
        name="方案设计师_A",
        agent_instance=create_mock_agent("方案设计师_A", "方案设计",
            "[方案A] 设计方案：采用微服务架构，优点是灵活可扩展，缺点是运维复杂度高"),
        role="方案设计",
        capabilities=["架构设计", "方案规划"],
        priority=2  # 优先级（用于选优）
    )
    
    swarm.register(
        name="方案设计师_B",
        agent_instance=create_mock_agent("方案设计师_B", "方案设计",
            "[方案B] 设计方案：采用单体架构+模块化，优点是开发快运维简单，缺点是扩展性受限"),
        role="方案设计",
        capabilities=["架构设计", "方案规划"],
        priority=1  # 最高优先级
    )
    
    swarm.register(
        name="方案设计师_C",
        agent_instance=create_mock_agent("方案设计师_C", "方案设计",
            "[方案C] 设计方案：采用Serverless架构，优点是按需付费免运维，缺点是冷启动延迟"),
        role="方案设计",
        capabilities=["架构设计", "方案规划"],
        priority=3
    )
    
    # 定义竞争任务
    task = "设计一个电商系统的技术架构方案"
    
    print(f"任务: {task}")
    print(f"竞争Agent: 方案设计师_A、方案设计师_B、方案设计师_C")
    print(f"协作模式: 竞争模式（Competition）")
    print(f"选优策略: 优先级排序（priority字段）")
    print()
    
    # 执行竞争协作
    result = swarm.run(
        task=task,
        pattern=CollaborationPattern.COMPETITION
    )
    
    print_result(result, "竞争结果")
    
    # 分析各方案
    print("=" * 60)
    print("方案对比分析")
    print("=" * 60)
    
    for name, profile in swarm.profiles.items():
        print(f"\n{name}:")
        print(f"  优先级: {profile.priority}")
        print(f"  能力: {profile.capabilities}")
        agent_result = swarm.blackboard.get(f"result_{name}")
        if agent_result:
            print(f"  方案摘要: {agent_result[:80]}...")
    
    return result


def explain_competition():
    """解释竞争模式"""
    print()
    print("=" * 60)
    print("竞争模式（Competition）解析")
    print("=" * 60)
    print("""
## 协作流程

1. 多个 Agent 并行执行相同任务
2. 各 Agent 独立生成方案/结果
3. 由选优机制选择最优结果
4. 输出最优方案

## 选优机制

1. **优先级排序**：按 Agent 的 priority 字段排序
2. **置信度排序**：按 Agent 返回结果的置信度排序
3. **投票机制**：多个评估 Agent 投票选出最优
4. **评分机制**：由评估 Agent 对各方案评分

## 关键设计点

1. **并行执行**：提高效率，同时生成多个方案
2. **独立性**：各 Agent 不应互相干扰
3. **选优公平**：选优机制应客观公正
4. **结果多样性**：鼓励 Agent 生成差异化方案

## 适用场景

- 方案设计：需要多种备选方案
- 创意生成：收集多样化创意
- 模型对比：对比不同模型效果

## 企业注意点

1. **成本倍增**：多个 Agent 并行，成本翻倍
2. **选优标准**：需要明确的选优规则
3. **方案融合**：可以融合多个方案的优点
4. **失败处理**：所有 Agent 都失败时的降级方案
""")


if __name__ == "__main__":
    demo_competition()
    explain_competition()