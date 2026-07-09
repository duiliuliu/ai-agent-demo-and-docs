"""
Demo 03: 辩论模式（正反方辩论后总结）

场景：正方、反方 Agent 辩论，第三方 Agent 总结仲裁
协作模式：DEBATE
通信方式：点对点（Peer-to-Peer）

适用场景：
  - 决策支持（方案利弊分析）
  - 风险评估（正反角度审视）
  - 复杂问题的多角度论证

运行方式：
  LLM_PROVIDER=mock python demo/03_debate.py        # Mock 模式
  LLM_PROVIDER=zhipu LLM_API_KEY=xxx python demo/03_debate.py  # 真实 LLM
"""
import os
import sys

demo_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(demo_dir)
sys.path.insert(0, os.path.join(skill_dir, "skill"))
sys.path.insert(0, demo_dir)

from demo_helper import create_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern


def demo_debate():
    """辩论模式演示"""
    print_config_info()
    
    # 创建辩论系统
    swarm = AgentSwarm(
        name="debate_panel",
        max_rounds=5,  # 最多5轮辩论
        communication_mode="peer_to_peer"
    )
    
    # 注册正方 Agent
    swarm.register(
        name="正方代表",
        agent_instance=create_agent("正方代表", "正方",
            system_prompt="你是辩论正方代表，请支持给定方案，列举优势。每轮发言控制在100字以内。"),
        role="正方",
        capabilities=["方案支持", "优势分析"]
    )
    
    # 注册反方 Agent
    swarm.register(
        name="反方代表",
        agent_instance=create_agent("反方代表", "反方",
            system_prompt="你是辩论反方代表，请反对给定方案，指出风险和问题。每轮发言控制在100字以内。"),
        role="反方",
        capabilities=["方案反对", "风险分析"]
    )
    
    # 注册仲裁者 Agent
    swarm.register(
        name="仲裁者",
        agent_instance=create_agent("仲裁者", "仲裁",
            system_prompt="你是辩论仲裁者，请综合正反双方观点，给出客观的结论和建议。"),
        role="仲裁者",
        capabilities=["观点总结", "方案裁决"]
    )
    
    # 定义辩论主题
    topic = "是否应该采用AI自动化客服系统替代人工客服"
    
    print(f"辩论主题: {topic}")
    print(f"正方Agent: 正方代表")
    print(f"反方Agent: 反方代表")
    print(f"仲裁Agent: 仲裁者")
    print(f"协作模式: 辩论模式（Debate）")
    print(f"最大辩论轮数: {swarm.max_rounds}")
    print()
    
    # 执行辩论
    result = swarm.run(
        task=topic,
        pattern=CollaborationPattern.DEBATE
    )
    
    print_result(result, "辩论结果")
    
    # 分析辩论流程
    messages = swarm.get_message_trace()
    debate_messages = [m for m in messages if 'debate' in m.get('message_type', '')]
    
    print("=" * 60)
    print("辩论流程追踪")
    print("=" * 60)
    print(f"总辩论消息数: {len(debate_messages)}")
    
    for i, msg in enumerate(debate_messages, 1):
        role = "正方" if msg['message_type'] == 'debate_pro' else "反方"
        print(f"\n第 {(i+1)//2} 轮 - {role}发言:")
        print(f"  {msg['sender']}: {msg['content'][:80]}...")
    
    return result


def explain_debate():
    """解释辩论模式"""
    print()
    print("=" * 60)
    print("辩论模式（Debate）解析")
    print("=" * 60)
    print("""
## 协作流程

1. 正方 Agent 发表支持观点
2. 反方 Agent 针对正方观点进行反驳
3. 正方 Agent 继续论证或回应反驳
4. 反方 Agent 继续反驳
5. 多轮辩论后，仲裁者 Agent 总结

## 关键设计点

1. **角色明确**：正方、反方、仲裁者职责分明
2. **结构化流程**：固定发言顺序，避免混乱
3. **反驳机制**：反方需针对正方观点，而非自由发言
4. **仲裁裁决**：最终由第三方总结，避免偏向

## 与平等协作的区别

辩论模式是平等协作的特殊形式：
- 有明确对立立场
- 有固定发言顺序（正→反→正→反）
- 有最终裁决者

## 适用场景

- 决策分析：方案利弊权衡
- 风险评估：多角度审视风险
- 合规审查：正反论证合规问题
- 技术选型：不同方案对比

## 企业注意点

1. **辩论轮次控制**：避免无限辩论，设置上限
2. **观点聚焦**：防止辩论偏离主题
3. **裁决权威性**：仲裁者应有足够的专业性
4. **结果落地**：辩论结论需要明确的行动建议
""")


if __name__ == "__main__":
    demo_debate()
    explain_debate()
