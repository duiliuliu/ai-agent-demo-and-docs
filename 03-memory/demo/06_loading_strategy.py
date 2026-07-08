"""Demo 6: 加载策略与时序演示

重点演示 MemoryLoader 的决策逻辑：
- 不同对话轮次下的加载策略变化
- 向量记忆的 ON_DEMAND 触发条件
- 用户画像的 CACHED 策略
- 长期记忆的 PARTIAL vs FULL 切换
- SKIP 策略的触发场景
- 自定义 Token 预算比例

核心问题：什么时候加载什么记忆？如何加载？消耗多少 Token？
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import MemoryManager, MemoryLoader, MemoryInjector, LoadStrategy


def print_decisions(decisions):
    """格式化打印加载决策"""
    for d in decisions:
        status = d["strategy"].upper()
        tokens = d["actual_tokens"]
        print(f"  {d['memory_type']:15s} | {status:10s} | {tokens:4d} tokens | {d['reason']}")


def main():
    print("=" * 60)
    print("Demo 6: 加载策略与时序演示")
    print("=" * 60)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    mm = MemoryManager("demo06_user")
    mm.long_term.storage_path = os.path.join(data_dir, "demo06_ltm.json")
    mm.long_term.clear()
    mm.vector_memory.storage_path = os.path.join(data_dir, "demo06_vm.json")
    mm.vector_memory.clear()
    mm.user_profile.storage_path = os.path.join(data_dir, "demo06_profile.json")
    mm.user_profile.clear()
    mm.clear_short_term()

    loader = MemoryLoader(total_token_budget=4000)
    injector = MemoryInjector(mm, loader)

    # 场景1: 空记忆状态（首轮对话）
    print("\n" + "═" * 55)
    print("场景 1: 空记忆状态（首轮对话）")
    print("═" * 55)
    result = injector.inject("你好", conversation_round=0, is_new_session=True)
    print("  用户输入: '你好'")
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print(f"\n  总 Token: {result['total_tokens']}")
    print("  分析: 所有记忆为空，大部分被 SKIP")

    # 添加数据
    mm.set_profile("姓名", "张三", "basic_info")
    mm.set_profile("城市", "北京", "basic_info")
    mm.user_profile.add_tag("美食家")
    mm.add_long_term("用户喜欢吃川菜")
    mm.add_long_term("用户上周查询了航班")
    mm.add_long_term("用户计划去杭州旅游")
    mm.add_long_term("用户对AI感兴趣")
    mm.add_long_term("用户使用iPhone")
    mm.add_long_term("用户偏好深色主题")
    mm.add_long_term("用户常驻北京朝阳")

    # 场景2: 有记忆 + 首轮 + 有查询意图
    print("\n" + "═" * 55)
    print("场景 2: 有记忆 + 首轮 + 有查询意图")
    print("═" * 55)
    loader.invalidate_cache()
    result = injector.inject("帮我推荐一些好吃的", conversation_round=0, is_new_session=True)
    print("  用户输入: '帮我推荐一些好吃的'")
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print(f"\n  总 Token: {result['total_tokens']}")
    print("  分析: 用户画像CACHED, 长期记忆PARTIAL, 向量ON_DEMAND触发, 短期记忆空")

    # 场景3: 第二轮（画像缓存命中 + 短期记忆有内容）
    mm.add_short_term("帮我推荐一些好吃的", "user")
    mm.add_short_term("推荐川菜馆：川办餐厅", "assistant")

    print("\n" + "═" * 55)
    print("场景 3: 第二轮对话（画像缓存命中）")
    print("═" * 55)
    result = injector.inject("那杭州的天气呢", conversation_round=1, is_new_session=False)
    print("  用户输入: '那杭州的天气呢'")
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print(f"\n  总 Token: {result['total_tokens']}")
    print("  分析: 画像缓存命中(0 tokens), 向量ON_DEMAND触发, 短期FULL")

    # 场景4: 简短回复（无查询意图）
    print("\n" + "═" * 55)
    print("场景 4: 简短回复（无查询意图 → 向量跳过）")
    print("═" * 55)
    result = injector.inject("好的谢谢", conversation_round=2, is_new_session=False)
    print("  用户输入: '好的谢谢'")
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print(f"\n  总 Token: {result['total_tokens']}")
    print("  分析: 输入短且无查询意图, 向量SKIP, 节省Token")

    # 场景5: 自定义预算比例
    print("\n" + "═" * 55)
    print("场景 5: 自定义 Token 预算比例")
    print("═" * 55)
    loader.update_ratios({
        "short_term": 0.3,
        "long_term": 0.3,
        "user_profile": 0.2,
        "vector": 0.2,
    })
    print("  新比例: short_term=30%, long_term=30%, profile=20%, vector=20%")
    loader.invalidate_cache()
    result = injector.inject("推荐北京的美食", conversation_round=0, is_new_session=True)
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print(f"\n  总 Token: {result['total_tokens']}")
    print("  分析: 向量预算增加, 可以召回更多相关记忆")

    # 场景6: 长期记忆很少（全量加载）
    print("\n" + "═" * 55)
    print("场景 6: 长期记忆少于 partial_limit → 全量加载")
    print("═" * 55)
    mm2 = MemoryManager("demo06_small")
    mm2.long_term.storage_path = os.path.join(data_dir, "demo06_ltm_small.json")
    mm2.long_term.clear()
    mm2.vector_memory.storage_path = os.path.join(data_dir, "demo06_vm_small.json")
    mm2.vector_memory.clear()
    mm2.long_term.add("用户喜欢吃川菜")
    mm2.long_term.add("用户在北京")
    # 只有2条，少于 partial_limit=5

    loader2 = MemoryLoader(total_token_budget=4000)
    injector2 = MemoryInjector(mm2, loader2)
    result = injector2.inject("推荐美食", conversation_round=0, is_new_session=True)
    print("  长期记忆条目数: 2 (< partial_limit=5)")
    print("\n  加载决策:")
    print_decisions(result["decisions"])
    print("  分析: 长期记忆用 FULL 而非 PARTIAL")

    # 清理
    mm.clear_all()
    mm2.clear_all()

    print("\n" + "=" * 60)
    print("Demo 6 完成")
    print("=" * 60)
    print("""
    核心总结：
    ┌──────────────┬─────────────┬──────────────────────────────┐
    │ 记忆类型      │ 加载策略    │ 触发条件                      │
    ├──────────────┼─────────────┼──────────────────────────────┤
    │ 用户画像      │ CACHED     │ 新会话加载, 后续缓存复用       │
    │ 长期记忆      │ PARTIAL    │ >N条时取最近N条; ≤N条时FULL   │
    │ 向量记忆      │ ON_DEMAND  │ 仅当检测到查询意图时触发搜索    │
    │ 短期记忆      │ FULL       │ 每轮都加载, 保证对话连贯       │
    └──────────────┴─────────────┴──────────────────────────────┘
    """)


if __name__ == "__main__":
    main()
