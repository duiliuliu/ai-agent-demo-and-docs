"""
Demo 08: 编排式讨论模式（Orchestrated Discussion）

场景：中心调度者动态决策发言顺序，每轮总结，判断是否继续
协作模式：ORCHESTRATED
通信方式：集中式（Centralized）

核心设计深度：
  1. 发言顺序决策：角色能力匹配 + 信息缺口评估 + 发言均衡度
  2. 每轮总结：关键信息、共识点、分歧点、信息缺口
  3. 终止判断：信息充足度、一致性、边际收益、轮次上限

适用场景：
  - 复杂问题深入讨论（需要多轮迭代）
  - 专家会诊（各领域专家按需发言）
  - 方案评审（调度者引导讨论方向）

运行方式：
  LLM_PROVIDER=mock python demo/08_orchestrated.py        # Mock 模式
  LLM_PROVIDER=zhipu LLM_API_KEY=xxx python demo/08_orchestrated.py  # 真实 LLM
"""
import os
import sys

# 路径配置
demo_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, demo_dir)

from demo_helper import create_agent, print_config_info, print_result
from skill.agent_swarm import AgentSwarm, CollaborationPattern


def demo_orchestrated():
    """编排式讨论模式演示"""
    print_config_info()

    # 创建协作系统（集中式通信，所有消息经过调度者）
    swarm = AgentSwarm(
        name="expert_panel",
        max_rounds=5,  # 最多5轮讨论
        communication_mode="centralized"
    )

    # 注册调度者（标记 is_coordinator=True）
    swarm.register(
        name="主持人",
        agent_instance=create_agent("主持人", "讨论调度",
            system_prompt="""你是讨论主持人/调度者，负责：
1. 根据讨论进展决定谁来发言
2. 每轮总结关键信息、共识、分歧、信息缺口
3. 判断讨论是否可以结束

请严格按照要求的格式输出，便于系统解析。"""),
        role="调度者",
        capabilities=["会议主持", "讨论引导", "总结归纳"],
        is_coordinator=True  # 标记为调度者
    )

    # 注册各领域专家（参与者）
    swarm.register(
        name="市场专家",
        agent_instance=create_agent("市场专家", "市场分析",
            system_prompt="你是市场分析专家，请从市场规模、用户需求、竞争格局角度分析问题。"),
        role="市场分析",
        capabilities=["市场调研", "用户研究", "竞品分析"]
    )

    swarm.register(
        name="技术专家",
        agent_instance=create_agent("技术专家", "技术评估",
            system_prompt="你是技术专家，请从技术可行性、架构设计、技术风险角度分析问题。"),
        role="技术评估",
        capabilities=["架构设计", "技术选型", "风险评估"]
    )

    swarm.register(
        name="产品专家",
        agent_instance=create_agent("产品专家", "产品规划",
            system_prompt="你是产品专家，请从用户体验、产品定位、功能规划角度分析问题。"),
        role="产品规划",
        capabilities=["产品设计", "需求分析", "路线图规划"]
    )

    swarm.register(
        name="财务专家",
        agent_instance=create_agent("财务专家", "财务分析",
            system_prompt="你是财务专家，请从成本收益、投资回报、财务风险角度分析问题。"),
        role="财务分析",
        capabilities=["成本核算", "收益预测", "投资评估"]
    )

    # 定义讨论任务
    task = "公司是否应该投入资源开发AI智能客服系统？请从市场、技术、产品、财务多角度综合评估。"

    print(f"讨论主题: {task}")
    print(f"调度者: 主持人")
    print(f"参与者: 市场专家、技术专家、产品专家、财务专家")
    print(f"协作模式: 编排式讨论（Orchestrated）")
    print(f"最大轮次: {swarm.max_rounds}")
    print()
    print("=" * 60)
    print("协作流程说明:")
    print("  第1轮: 所有专家依次发言（收集基础信息）")
    print("  第2轮起: 调度者动态决定发言顺序（信息缺口驱动）")
    print("  每轮结束: 调度者总结 + 判断是否继续")
    print("=" * 60)
    print()

    # 执行编排式讨论
    result = swarm.run(
        task=task,
        pattern=CollaborationPattern.ORCHESTRATED
    )

    print_result(result, "编排式讨论结果")

    # 详细展示讨论过程
    print("=" * 60)
    print("讨论过程追踪")
    print("=" * 60)

    messages = swarm.get_message_trace()
    current_round = 0

    for msg in messages:
        msg_type = msg.get('message_type', '')
        sender = msg.get('sender', '?')
        content = str(msg.get('content', ''))
        metadata = msg.get('metadata', {})
        round_num = metadata.get('round', 0)

        if round_num != current_round:
            current_round = round_num
            print(f"\n--- 第 {current_round} 轮 ---")

        if msg_type == 'orchestrated_speak':
            preview = content[:120] + "..." if len(content) > 120 else content
            print(f"  [发言] {sender}: {preview}")

        elif msg_type == 'round_summary':
            print(f"  [总结] {sender}: {content[:150]}...")

        elif msg_type == 'continue_decision':
            should_continue = metadata.get('should_continue', True)
            decision = "继续讨论" if should_continue else "终止讨论"
            reason = ""
            try:
                content_dict = eval(content) if isinstance(content, str) and content.startswith('{') else {}
                reason = content_dict.get('reason', '') if isinstance(content_dict, dict) else ''
            except:
                pass
            print(f"  [决策] {decision} - {reason[:80]}")

    # 输出各Agent发言统计
    print()
    print("=" * 60)
    print("各 Agent 发言统计")
    print("=" * 60)
    for name, profile in swarm.profiles.items():
        if profile.is_coordinator:
            continue
        print(f"  {name}: 发言 {profile.speak_count} 次")

    return result


def explain_orchestrated():
    """解释编排式讨论模式"""
    print()
    print("=" * 60)
    print("编排式讨论模式（Orchestrated）深度解析")
    print("=" * 60)
    print("""
## 一、模式定位

编排式讨论是 Round Robin 平等协作的进化版：
- Round Robin: 固定顺序，机械轮询
- Orchestrated: 智能调度，动态调整

调度者不直接产出内容，而是做"元决策"——决定谁发言、什么时候停。

## 二、发言顺序决策：依据与驱动机制

### 2.1 五个决策维度

| 维度 | 说明 | 评估方式 |
|------|------|----------|
| 角色能力匹配 | 当前需要什么信息，哪个Agent最匹配 | 能力标签 + 任务阶段 |
| 信息缺口评估 | 已有信息覆盖了哪些，还缺什么 | 调度者LLM智能判断 |
| 依赖关系链 | 某些角色输出是另一些的输入 | 预设依赖图 / LLM推理 |
| 发言均衡度 | 防止过度调用或冷落某个Agent | speak_count 统计 |
| 历史质量 | 哪个Agent过往发言质量高 | quality_score 动态评分 |

### 2.2 调度策略（混合策略）

**第1轮：依赖链驱动**
- 按预设的角色依赖顺序发言
- 目的：收集基础信息，建立共同认知
- 顺序通常：数据 → 分析 → 方案 → 决策

**第2轮起：信息缺口驱动 + 均衡度修正**
- 70% 权重：填补最大信息缺口的角色
- 30% 权重：发言次数最少的角色（保障多样性）
- 由调度者LLM综合判断，输出结构化的发言顺序

### 2.3 调度Prompt设计要点

1. 提供完整上下文：任务、参与者信息、历史讨论
2. 明确决策维度：告诉调度者从哪些角度思考
3. 结构化输出：便于程序解析（【发言顺序】【调度理由】）
4. 容错机制：解析失败时fallback到默认顺序

## 三、总结与终止判断

### 3.1 每轮总结的四个维度

1. **关键信息**：本轮获得了哪些新的重要信息
2. **共识点**：大家在哪些方面达成了一致
3. **分歧点**：主要的争议或不同意见
4. **信息缺口**：还缺少哪些关键信息

→ 总结不仅是回顾，更是为下一轮调度提供依据

### 3.2 终止判断的三个评分维度

| 维度 | 高分含义 | 低分含义 |
|------|----------|----------|
| 信息充足度 | 已有足够信息回答问题 | 还需要更多信息 |
| 一致性 | 各Agent观点趋于一致 | 存在重大分歧 |
| 边际收益 | 继续讨论收获不大 | 还会有显著新信息 |

### 3.3 终止条件（满足任一即终止）

1. **硬限制**：达到 max_rounds（成本控制）
2. **信息充足**：调度者评估信息充足度 ≥ 阈值
3. **共识达成**：一致性评分 ≥ 阈值
4. **边际递减**：连续两轮边际收益低
5. **主动终止**：调度者综合判断可结束

### 3.4 最少轮次保障

- 至少2轮才考虑终止
- 第1轮：收集基础信息
- 第2轮：深入讨论 + 首次评估
- 避免"讨论还没开始就结束了"

## 四、与其他模式的对比

| 模式 | 调度方式 | 终止条件 | 适用场景 |
|------|----------|----------|----------|
| Round Robin | 固定顺序 | 轮次/简单共识 | 头脑风暴 |
| Hierarchical | 主Agent分解 | 任务完成 | 任务执行 |
| Debate | 正→反→正→反 | 固定轮次 | 决策分析 |
| **Orchestrated** | **调度者动态决策** | **信息充足/边际收益** | **复杂问题深入讨论** |

## 五、企业级注意点

### 5.1 调度者能力要求高
- 调度者需要理解各领域的基本概念
- 需要能评估信息完备性
- 建议使用能力更强的模型

### 5.2 调度者瓶颈
- 所有决策都经过调度者
- 每轮至少3次调度者调用（决策/总结/判断）
- 成本较高，适合高价值讨论

### 5.3 可观测性
- 记录每次调度决策及其理由
- 记录终止判断的三个评分
- 便于事后审计和优化

### 5.4 降级策略
- 调度者失效时，自动降级为 Round Robin
- 调度者输出格式错误时，fallback到默认策略
- 保证系统鲁棒性

### 5.5 调度偏差
- 调度者可能有偏见（偏好某类专家）
- 发言均衡度机制可部分缓解
- 重要讨论可人工审核调度决策
""")


if __name__ == "__main__":
    demo_orchestrated()
    explain_orchestrated()
