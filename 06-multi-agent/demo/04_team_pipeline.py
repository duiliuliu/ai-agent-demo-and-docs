"""
Demo 04: 团队流水线模式（Pipeline Collaboration）

场景：Agent 按角色顺序依次处理，形成协作流水线
协作模式：TEAM_PIPELINE
通信方式：共享黑板（Blackboard）

适用场景：
  - 内容生产流水线（研究→分析→撰写→审查）
  - 数据处理流水线（采集→清洗→分析→可视化）
  - 审批流程（提交→初审→复审→终审）

运行方式：
  LLM_PROVIDER=mock python demo/04_team_pipeline.py        # Mock 模式
  LLM_PROVIDER=zhipu LLM_API_KEY=xxx python demo/04_team_pipeline.py  # 真实 LLM
"""
import os
import sys

demo_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(demo_dir)
sys.path.insert(0, os.path.join(skill_dir, "skill"))
sys.path.insert(0, demo_dir)

from demo_helper import create_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern


def demo_team_pipeline():
    """团队流水线模式演示"""
    print_config_info()
    
    # 创建流水线协作系统（共享黑板通信）
    swarm = AgentSwarm(
        name="content_pipeline",
        max_rounds=10,
        communication_mode="blackboard"
    )
    
    # 注册流水线 Agent（按处理顺序注册）
    
    # Stage 1: 研究员
    swarm.register(
        name="研究员",
        agent_instance=create_agent("研究员", "研究",
            system_prompt="你是研究员，负责收集和整理信息。请简要列出你收集到的关键数据和发现。"),
        role="研究",
        capabilities=["信息收集", "行业研究"]
    )
    
    # Stage 2: 数据分析师
    swarm.register(
        name="数据分析师",
        agent_instance=create_agent("数据分析师", "数据分析",
            system_prompt="你是数据分析师，负责分析数据并提取洞察。请给出关键趋势和结论。"),
        role="数据分析",
        capabilities=["数据处理", "统计分析"]
    )
    
    # Stage 3: 内容撰写员
    swarm.register(
        name="撰写员",
        agent_instance=create_agent("撰写员", "撰写",
            system_prompt="你是内容撰写员，负责基于分析结果撰写报告。请给出报告的主要章节和内容摘要。"),
        role="撰写",
        capabilities=["文案写作", "报告撰写"]
    )
    
    # Stage 4: 编辑审核员
    swarm.register(
        name="编辑",
        agent_instance=create_agent("编辑", "编辑",
            system_prompt="你是编辑审核员，负责检查和优化内容。请给出审核意见和优化建议。"),
        role="编辑",
        capabilities=["内容审核", "语言优化"]
    )
    
    # Stage 5: 质量检查员
    swarm.register(
        name="质检员",
        agent_instance=create_agent("质检员", "质检",
            system_prompt="你是质量检查员，负责最终质量把关。请给出质检结论。"),
        role="质检",
        capabilities=["质量检查", "合规审核"]
    )
    
    # 定义流水线任务
    task = "制作一份AI行业发展报告"
    
    print(f"任务: {task}")
    print(f"流水线阶段: 研究员 → 数据分析师 → 撰写员 → 编辑 → 质检员")
    print(f"协作模式: 团队流水线（Team Pipeline）")
    print()
    
    # 执行协作
    result = swarm.run(
        task=task,
        pattern=CollaborationPattern.TEAM_PIPELINE
    )
    
    print_result(result, "流水线执行结果")
    
    # 分析流水线各阶段
    print("=" * 60)
    print("流水线阶段分析")
    print("=" * 60)
    
    messages = swarm.get_message_trace()
    pipeline_messages = [m for m in messages if m.get('message_type') == 'pipeline_output']
    
    for i, msg in enumerate(pipeline_messages, 1):
        print(f"\n阶段 {i}: {msg['sender']}")
        print(f"  输出: {msg['content'][:80]}...")
    
    return result


def explain_pipeline():
    """解释流水线模式"""
    print()
    print("=" * 60)
    print("团队流水线模式（Team Pipeline）解析")
    print("=" * 60)
    print("""
## 协作流程

1. 第一个 Agent 处理原始任务
2. 第二个 Agent 接收第一个 Agent 的输出
3. 第三个 Agent 接收第二个 Agent 的输出
4. 以此类推，直到最后一个 Agent 完成最终输出

## 关键设计点

1. **顺序依赖**：后一阶段依赖前一阶段的输出
2. **角色分工**：每个 Agent 有明确职责
3. **增量处理**：每个 Agent 在前人基础上完善
4. **最终输出**：流水线最后一个 Agent 的输出为最终结果

## 与其他模式的区别

| 模式 | 任务关系 | 通信方式 | 适用场景 |
|------|----------|----------|----------|
| 流水线 | 串行依赖 | 黑板共享 | 内容生产 |
| 主子 | 并行独立 | 集中式 | 任务分解 |
| 辩论 | 对立交互 | 点对点 | 决策支持 |

## 适用场景

- 内容生产：研究→分析→撰写→审核
- 数据处理：采集→清洗→分析→可视化
- 审批流程：提交→初审→复审→终审

## 企业注意点

1. **阶段故障**：任一阶段失败，整个流水线受阻，需要错误处理
2. **效率瓶颈**：串行执行，总耗时为各阶段之和
3. **中间状态管理**：黑板数据需要版本控制和清理
4. **质量门禁**：每个阶段应有质量检查点，不合格则退回
""")


if __name__ == "__main__":
    demo_team_pipeline()
    explain_pipeline()
