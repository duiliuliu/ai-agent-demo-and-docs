"""
Demo 01: 轮流发言的极简多 Agent（平等协作模式）

场景：多个 Agent 平等地位，轮流发言，共同讨论一个问题
协作模式：ROUND_ROBIN
通信方式：点对点（Peer-to-Peer）

适用场景：
  - 头脑风暴
  - 多角度分析问题
  - 共识达成

运行方式：
  LLM_PROVIDER=mock python demo/01_round_robin.py        # Mock 模式
  LLM_PROVIDER=zhipu LLM_API_KEY=xxx python demo/01_round_robin.py  # 真实 LLM
"""
import os
import sys

# 路径配置
demo_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(demo_dir)
sys.path.insert(0, os.path.join(skill_dir, "skill"))  # 添加 skill 目录

from demo_helper import create_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern


def demo_round_robin():
    """平等协作模式演示"""
    print_config_info()
    
    # 创建协作系统
    swarm = AgentSwarm(
        name="brainstorm_team",
        max_rounds=3,
        communication_mode="peer_to_peer"
    )
    
    # 注册多个 Agent（平等地位）
    # 使用 create_agent 自动选择真实 LLM 或 Mock
    swarm.register(
        name="市场分析师",
        agent_instance=create_agent("市场分析师", "分析师",
            system_prompt="你是一个市场分析师，请从市场角度分析问题，关注用户需求和竞争格局"),
        role="分析师",
        capabilities=["市场分析", "竞品研究"]
    )
    
    swarm.register(
        name="技术专家",
        agent_instance=create_agent("技术专家", "技术顾问",
            system_prompt="你是一个技术专家，请从技术角度分析问题，关注系统架构和技术可行性"),
        role="技术顾问",
        capabilities=["技术评估", "架构设计"]
    )
    
    swarm.register(
        name="产品经理",
        agent_instance=create_agent("产品经理", "产品规划",
            system_prompt="你是一个产品经理，请从产品角度分析问题，平衡用户体验和业务目标"),
        role="产品规划",
        capabilities=["产品设计", "需求分析"]
    )
    
    # 定义讨论任务
    task = "分析一个智能客服系统的设计方案"
    
    print(f"讨论主题: {task}")
    print(f"参与Agent: {list(swarm.agents.keys())}")
    print(f"协作模式: 平等协作（Round Robin）")
    print()
    
    # 执行协作
    result = swarm.run(
        task=task,
        pattern=CollaborationPattern.ROUND_ROBIN
    )
    
    print_result(result, "协作讨论结果")
    
    # 输出通信追踪
    messages = swarm.get_message_trace()
    print(f"通信消息数量: {len(messages)}")
    
    return result


def explain_round_robin():
    """解释平等协作模式"""
    print("=" * 60)
    print("平等协作模式（Round Robin）解析")
    print("=" * 60)
    print("""
## 协作流程

1. 所有 Agent 平等地位，没有主从关系
2. 按注册顺序轮流发言
3. 每个 Agent 可以看到前面 Agent 的观点
4. 通过多轮讨论，逐步达成共识

## 关键设计点

1. **无中心调度**：没有主 Agent 控制流程
2. **上下文传递**：当前 Agent 可访问历史讨论内容
3. **共识检测**：检查最后几轮输出是否相似
4. **轮次限制**：防止无限讨论

## 适用场景

- 头脑风暴：收集多样化观点
- 多角度分析：从不同专业视角审视问题
- 共识达成：通过讨论形成一致意见

## 企业注意点

1. **通信风暴**：限制轮次，避免消息爆炸
2. **共识仲裁**：当无法达成共识时，需要仲裁机制
3. **成本控制**：每轮调用所有 Agent，成本线性增长
4. **角色差异化**：Agent 角色应有明显差异，避免重复发言
""")


if __name__ == "__main__":
    demo_round_robin()
    explain_round_robin()
