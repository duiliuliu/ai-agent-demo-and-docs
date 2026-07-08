"""Demo 2: 长期记忆

演示：
- 持久化存储到文件
- 关键词搜索
- 增删改查
- 跨会话加载验证
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import LongTermMemory


def main():
    print("=" * 60)
    print("Demo 2: 长期记忆")
    print("=" * 60)

    # 使用临时路径避免污染
    ltm = LongTermMemory(storage_path=os.path.join(os.path.dirname(__file__), "..", "data", "demo02_ltm.json"))
    ltm.clear()

    print("\n[1] 添加长期记忆")
    memories = [
        "用户偏好川菜，喜欢辣的食物",
        "上周查询了北京到上海的航班",
        "用户提到周末计划去杭州旅游",
        "用户对AI技术很感兴趣",
        "用户使用iPhone",
    ]
    for m in memories:
        ltm.add(m)
        print(f"  + {m}")

    print(f"\n  条目数: {ltm.size()}, Token: {ltm.estimate_tokens()}")

    print("\n[2] 关键词搜索")
    for kw in ["航班", "杭州", "川菜"]:
        results = ltm.search(kw)
        print(f"  搜索'{kw}': {[e.content[:15] for e, _ in results]}")

    print("\n[3] 更新记忆")
    print(f"  更新前[0]: {ltm.get()[0].content}")
    ltm.update_entry(0, "用户偏好川菜和湘菜，喜欢辣的食物")
    print(f"  更新后[0]: {ltm.get()[0].content}")

    print("\n[4] 删除记忆")
    ltm.delete_entry(1)
    print(f"  删除后条目数: {ltm.size()}")

    print("\n[5] 上下文输出")
    print(f"  {ltm.to_context(limit=3)}")

    print("\n[6] 持久化验证：重新加载")
    ltm2 = LongTermMemory(storage_path=ltm.storage_path)
    print(f"  重新加载条目数: {ltm2.size()}")
    print(f"  第一条: {ltm2.get()[0].content}")

    # 清理
    ltm.clear()
    ltm2.clear()

    print("\n" + "=" * 60)
    print("Demo 2 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
