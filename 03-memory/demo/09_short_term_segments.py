"""Demo 9: 短期记忆会话段降噪与滚动

演示 ShortTermMemory 的会话段（SessionSegment）机制：
- 消息累积到当前活跃段
- 段边界检测（超 Token / 超时 / 手动结束）
- 段结束时信息密度评分
- 低密度段自动丢弃
- 高密度段进入历史保留
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import ShortTermMemory


def main():
    print("=" * 60)
    print("Demo 9: 短期记忆会话段降噪与滚动")
    print("=" * 60)

    # max_segments=3, 保留最近3个段
    stm = ShortTermMemory(
        max_segments=3,
        max_tokens_per_segment=200,
        segment_timeout_minutes=5,
        density_threshold=0.3
    )

    print("\n[1] 模拟一个低密度段（闲聊+确认）- 应被丢弃")
    # 噪音段
    stm.add_message("user", "嗯")
    stm.add_message("assistant", "好的")
    stm.add_message("user", "哈哈")
    stm.add_message("assistant", "是的")
    # 手动结束当前段
    stm.force_finalize()
    print(f"  段数: {stm.segment_count()}, 消息数: {stm.size()}")
    print(f"  说明: 密度太低的段被丢弃")

    print("\n[2] 模拟一个高密度段（实际任务对话）- 应被保留")
    stm.add_message("user", "你好，我想查北京天气", topic="天气查询")
    stm.add_message("assistant", "北京今天晴，28°C")
    stm.add_message("user", "明天呢？")
    stm.add_message("assistant", "明天多云转晴，26°C")
    stm.add_message("user", "上海呢？")
    stm.add_message("assistant", "上海多云，30°C")
    stm.force_finalize()
    print(f"  段数: {stm.segment_count()}, 消息数: {stm.size()}")
    print(f"  说明: 包含天气查询的高密度段被保留")

    print("\n[3] 模拟一个偏好类段（最高信息价值）")
    stm.add_message("user", "我最近想改吃粤菜", topic="饮食偏好")
    stm.add_message("assistant", "好的，记下了")
    stm.add_message("user", "而且我决定用Mac了", topic="设备偏好")
    stm.add_message("assistant", "收到，已记录")
    stm.force_finalize()
    print(f"  段数: {stm.segment_count()}, 消息数: {stm.size()}")

    print("\n[4] 模拟致谢型段（低价值）")
    stm.add_message("user", "谢谢")
    stm.add_message("assistant", "不客气")
    stm.add_message("user", "好的，再见")
    stm.add_message("assistant", "再见")
    stm.force_finalize()
    print(f"  段数: {stm.segment_count()}, 消息数: {stm.size()}")

    print("\n[5] 模拟连续多段，超过 max_segments=3 会滚动淘汰")
    for i in range(5):
        stm.add_message("user", f"第{i+1}个新段-查询", topic=f"任务{i+1}")
        stm.add_message("assistant", f"第{i+1}个新段-回答")
        stm.add_message("user", f"好的，知道了")
        stm.force_finalize()
    print(f"  最终段数: {stm.segment_count()} (max=3, 老的被淘汰)")

    print("\n[6] 查看保留的会话段")
    print(stm.to_context())

    print("\n[7] 单段 Token 限制演示")
    stm2 = ShortTermMemory(max_segments=5, max_tokens_per_segment=50, density_threshold=0.0)
    for i in range(10):
        stm2.add_message("user", f"这是一条测试消息，编号{i:02d}，内容比较长用于测试Token限制")
    stm2.force_finalize()
    print(f"  添加10条长消息后, 段数: {stm2.segment_count()}")
    print(f"  说明: 单段超50 tokens 自动结束，开始新段")

    print("\n[8] 与老版本对比")
    print("""
    老版本（按时间过期）:
      - 问题：用户的"改吃粤菜"可能被闲聊消息挤出窗口
      - 问题：噪音消息占用 Token 配额
      
    新版本（按会话段滚动+降噪）:
      - 噪音段直接丢弃，节省 Token
      - 偏好类信息即使混杂在噪音中也可能保留（因段整体密度够）
      - 每个段保持话题内聚性，便于 LLM 理解
    """)

    print("\n" + "=" * 60)
    print("Demo 9 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
