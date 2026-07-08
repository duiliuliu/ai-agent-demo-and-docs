"""Demo 5: 多记忆协同 + 多轮意图对话

演示完整流程：
1. 初始化用户画像 + 长期记忆
2. 模拟多轮对话，每轮：
   - MemoryLoader 决策加载哪些记忆
   - MemoryInjector 执行加载并构建 Prompt 上下文
   - 模拟 LLM 响应
   - 更新短期记忆
3. 每轮打印加载决策、Token 消耗、最终 Prompt
4. 最后演示短期→长期记忆转换
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import MemoryManager, MemoryLoader, MemoryInjector


def simulate_llm(context: str, user_input: str) -> str:
    """模拟 LLM 响应（基于上下文中的记忆做条件判断）"""
    if "川菜" in context and "美食" in user_input:
        return "根据您偏好川菜的特点，推荐'川办餐厅'和'大董'。"
    if "杭州" in context and "天气" in user_input:
        return "杭州今天晴，25°C，适合旅游。"
    if "航班" in context and "机票" in user_input:
        return "我来帮您查北京到上海的航班，请告诉我出行日期。"
    if "人工智能" in context and "AI" in user_input:
        return "最近大语言模型和多模态AI发展很快，您感兴趣的话我可以详细讲讲。"
    return "好的，我了解了您的需求。"


def main():
    print("=" * 60)
    print("Demo 5: 多记忆协同 + 多轮意图对话")
    print("=" * 60)

    # 使用临时存储避免污染
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    mm = MemoryManager("demo05_user")
    mm.long_term.storage_path = os.path.join(data_dir, "demo05_ltm.json")
    mm.long_term.clear()
    mm.vector_memory.storage_path = os.path.join(data_dir, "demo05_vm.json")
    mm.vector_memory.clear()
    mm.user_profile.storage_path = os.path.join(data_dir, "demo05_profile.json")
    mm.user_profile.clear()
    mm.clear_short_term()

    loader = MemoryLoader(total_token_budget=4000)
    injector = MemoryInjector(mm, loader)

    # 初始化用户画像
    print("\n[1] 初始化用户画像")
    mm.set_profile("姓名", "张三", "basic_info")
    mm.set_profile("城市", "北京", "basic_info")
    mm.set_profile("喜欢川菜", True, "preferences")
    mm.user_profile.add_tag("旅游爱好者")
    print("  画像已设置")

    # 初始化长期记忆
    print("\n[2] 添加长期记忆（同时写入向量索引）")
    facts = [
        "用户喜欢吃川菜，偏好辣的食物",
        "用户上周查询过北京到上海的航班",
        "用户提到周末要去杭州旅游",
        "用户对人工智能技术很感兴趣",
    ]
    for f in facts:
        mm.add_long_term(f)
        print(f"  + {f}")

    # 多轮对话
    print("\n[3] 多轮对话模拟")
    conversation = [
        "你好，我想找一些好吃的川菜",
        "好的，杭州的天气怎么样？",
        "帮我查一下机票吧",
        "最近有什么AI方面的新闻吗？",
        "你还记得我喜欢什么菜吗？",
    ]

    for round_num, user_input in enumerate(conversation):
        print(f"\n{'─' * 50}")
        print(f"  对话轮次 {round_num + 1}")
        print(f"  用户: {user_input}")
        print(f"{'─' * 50}")

        # 记忆加载决策 + 注入
        is_new = (round_num == 0)
        result = injector.inject(user_input, conversation_round=round_num, is_new_session=is_new)

        # 打印加载决策
        print("\n  [加载决策]")
        for d in result["decisions"]:
            status = "✓ 加载" if d["actual_tokens"] > 0 else "✗ 跳过"
            print(f"    {d['memory_type']:15s} | {d['strategy']:10s} | {status} | {d['reason']}")

        # 打印 Token 消耗
        print(f"\n  [Token 消耗]")
        for mem_type, tokens in result["token_usage"].items():
            if tokens > 0:
                print(f"    {mem_type:15s}: {tokens} tokens")
        print(f"    {'总计':15s}: {result['total_tokens']} tokens")

        # 模拟 LLM 响应
        response = simulate_llm(result["context"], user_input)
        print(f"\n  [助手]: {response}")

        # 更新短期记忆
        mm.add_short_term(user_input, "user")
        mm.add_short_term(response, "assistant")

    # Token 预算分析
    print(f"\n{'═' * 50}")
    print("[4] Token 预算分配策略")
    print(f"{'═' * 50}")
    ratios = loader.get_ratios()
    for k, v in ratios.items():
        budget = int(loader.total_token_budget * v)
        print(f"  {k:15s}: {v*100:.0f}%  ({budget} tokens)")

    # 短期→长期转换
    print(f"\n{'═' * 50}")
    print("[5] 短期→长期记忆转换")
    print(f"{'═' * 50}")
    print(f"  转换前: 短期 {mm.short_term.size()}条 / {mm.short_term.estimate_tokens()} tokens")
    print(f"          长期 {mm.long_term.size()}条 / {mm.long_term.estimate_tokens()} tokens")
    committed = mm.commit_short_to_long(min_tokens=100)
    print(f"  转换后: 已提交 {committed} 条到长期记忆")
    print(f"          短期 {mm.short_term.size()}条 / {mm.short_term.estimate_tokens()} tokens")
    print(f"          长期 {mm.long_term.size()}条 / {mm.long_term.estimate_tokens()} tokens")

    # 最终记忆摘要
    print(f"\n{'═' * 50}")
    print("[6] 最终记忆摘要")
    print(f"{'═' * 50}")
    summary = mm.get_token_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # 清理
    mm.clear_all()

    print("\n" + "=" * 60)
    print("Demo 5 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
