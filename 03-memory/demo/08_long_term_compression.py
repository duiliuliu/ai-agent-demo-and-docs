"""Demo 8: 长期记忆压缩与去噪

演示 MemoryCompressor 的四种决策：
- SKIP: 噪音消息不入库
- MERGE: 与已有记忆合并（如"喜欢川菜" + "喜欢湘菜" → 合并）
- REPLACE: 覆盖旧记忆（如"喜欢川菜" → "改吃粤菜了"）
- APPEND: 追加为新记忆
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import MemoryCompressor, CompressAction, LongTermMemory


def main():
    print("=" * 60)
    print("Demo 8: 长期记忆压缩与去噪")
    print("=" * 60)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    ltm = LongTermMemory(storage_path=os.path.join(data_dir, "demo08_ltm.json"))
    ltm.clear()

    print("\n[1] 测试噪音过滤（应 SKIP）")
    noise_inputs = [
        "嗯",
        "好的",
        "OK",
        "谢谢",
        "哈哈",
        "...",
        "?",
    ]
    for noise in noise_inputs:
        success, reason = ltm.add(noise)
        status = "✓ 入库" if success else "✗ 跳过"
        print(f"  {status:8s} | '{noise}' | {reason}")

    print(f"\n  当前长期记忆条目数: {ltm.size()}")

    print("\n[2] 测试 APPEND（正常新记忆）")
    new_inputs = [
        "用户喜欢吃川菜",
        "用户对AI技术很感兴趣",
        "用户上周查询了北京天气",
    ]
    for inp in new_inputs:
        success, reason = ltm.add(inp)
        print(f"  {'✓ 入库' if success else '✗ 跳过':8s} | '{inp}' | {reason}")

    print(f"\n  当前长期记忆条目数: {ltm.size()}")

    print("\n[3] 测试 MERGE（相似内容自动合并）")
    merge_inputs = [
        "用户喜欢吃湘菜",        # 与"川菜"高相似
        "用户喜欢湘菜和川菜",    # 与"川菜"高相似
        "用户对AI新技术很感兴趣", # 与"AI技术"高相似
    ]
    for inp in merge_inputs:
        success, reason = ltm.add(inp)
        print(f"  {'✓ 合并' if success else '✗ 跳过':8s} | '{inp}' | {reason}")

    print(f"\n  当前长期记忆条目数: {ltm.size()}（应该没增加很多）")
    print("\n  当前长期记忆内容:")
    for i, entry in enumerate(ltm._entries):
        print(f"    [{i}] {entry.content}")

    print("\n[4] 测试 REPLACE（覆盖旧记忆）")
    replace_inputs = [
        "用户改吃粤菜了，不喜欢川菜了",  # 覆盖"川菜"相关
        "用户对机器学习不感兴趣，改关注区块链",  # 覆盖"AI"相关
    ]
    for inp in replace_inputs:
        success, reason = ltm.add(inp)
        print(f"  {'✓ 覆盖' if success else '✗ 跳过':8s} | '{inp}' | {reason}")

    print(f"\n  当前长期记忆内容:")
    for i, entry in enumerate(ltm._entries):
        print(f"    [{i}] {entry.content}")

    print("\n[5] 噪音混入压力测试")
    noisy_inputs = [
        "嗯", "好的",  # 噪音
        "用户计划明年去日本旅游",  # 新事实
        "哦", "哈哈",  # 噪音
        "用户提到了他的妻子",  # 新事实
    ]
    for inp in noisy_inputs:
        success, reason = ltm.add(inp)
        print(f"  {'✓' if success else '✗':4s} | '{inp}' | {reason}")

    print(f"\n  最终条目数: {ltm.size()}")

    print("\n[6] 批量压缩演示")
    batch = [
        "用户养了一只猫",
        "嗯",  # 噪音
        "用户养了一只英短猫",  # 合并
        "哦",  # 噪音
        "用户改养狗了",  # 覆盖
    ]
    compressor = MemoryCompressor()
    results = compressor.batch_compress(batch)
    print("\n  批量决策:")
    for content, result in zip(batch, results):
        print(f"    {result.action.value:8s} | '{content}' | {result.reason}")

    # 清理
    ltm.clear()

    print("\n" + "=" * 60)
    print("Demo 8 完成")
    print("=" * 60)
    print("""
    核心要点：
    - SKIP   : 噪音消息自动过滤，不污染长期记忆
    - MERGE  : 相似内容自动合并（如"喜欢川菜" + "喜欢湘菜"）
    - REPLACE: 检测到覆盖信号（"改"、"不"等）时覆盖旧记忆
    - APPEND : 真正的新信息才追加
    """)


if __name__ == "__main__":
    main()
