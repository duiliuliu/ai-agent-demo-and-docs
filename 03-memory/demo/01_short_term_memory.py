"""Demo 1: 短期记忆基础

演示：
- 添加对话消息到短期记忆
- 滑动窗口自动驱逐旧消息
- Token 限制保护
- 生成对话历史上下文
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import ShortTermMemory


def main():
    print("=" * 60)
    print("Demo 1: 短期记忆基础")
    print("=" * 60)

    stm = ShortTermMemory(max_entries=5, max_tokens=200)

    print("\n[1] 添加 3 轮对话")
    stm.add_message("user", "你好，查北京天气")
    stm.add_message("assistant", "北京今天晴，28°C")
    stm.add_message("user", "明天呢？")
    stm.add_message("assistant", "明天多云，26°C")

    print(f"  条目数: {stm.size()}, Token: {stm.estimate_tokens()}")
    print(f"  上下文:\n{stm.to_context()}")

    print("\n[2] 超过 max_entries=5，自动驱逐最旧")
    for i in range(4):
        stm.add_message("user", f"第{i+3}轮对话内容")
    print(f"  条目数: {stm.size()} (上限 5)")
    print(f"  最新上下文:\n{stm.to_context()}")

    print("\n[3] 对话历史格式（OpenAI 格式）")
    for msg in stm.get_conversation_history():
        print(f"  {msg}")

    print("\n[4] 清空记忆")
    stm.clear()
    print(f"  清空后条目数: {stm.size()}")

    print("\n" + "=" * 60)
    print("Demo 1 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
