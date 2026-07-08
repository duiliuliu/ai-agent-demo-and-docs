"""Demo 4: 向量化记忆

演示：
- 文本向量化（字符级分词）
- 混合相似度搜索（余弦 60% + Jaccard 40%）
- 更新/删除后向量索引同步
- 不同查询的召回结果对比
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import VectorMemory


def main():
    print("=" * 60)
    print("Demo 4: 向量化记忆")
    print("=" * 60)

    vm = VectorMemory(storage_path=os.path.join(os.path.dirname(__file__), "..", "data", "demo04_vm.json"))
    vm.clear()

    print("\n[1] 添加向量化记忆")
    memories = [
        "用户喜欢吃川菜，偏好辣的食物",
        "用户上周查询过北京到上海的航班",
        "用户提到周末要去杭州旅游",
        "用户对人工智能技术很感兴趣",
        "用户使用苹果手机",
        "北京今天天气晴朗，温度28度",
        "杭州西湖风景优美，适合旅游",
    ]
    for m in memories:
        vm.add(m)
        print(f"  + {m}")

    print(f"\n  条目数: {vm.size()}")

    print("\n[2] 语义搜索对比")
    queries = ["北京天气", "旅行计划", "人工智能", "手机品牌", "美食推荐"]
    for q in queries:
        results = vm.search(q, top_k=3)
        print(f"\n  查询: '{q}'")
        if results:
            for entry, score in results:
                print(f"    [{score:.4f}] {entry.content}")
        else:
            print("    无匹配结果")

    print("\n[3] 更新记忆后重新搜索")
    vm.update_entry(0, "用户喜欢吃川菜和湘菜，偏好辣的食物")
    print(f"  更新后[0]: {vm.get()[0].content}")
    results = vm.search("美食", top_k=3)
    print(f"  搜索'美食':")
    for entry, score in results:
        print(f"    [{score:.4f}] {entry.content}")

    print("\n[4] 删除记忆后验证索引同步")
    print(f"  删除前条目数: {vm.size()}")
    vm.delete_entry(1)
    print(f"  删除后条目数: {vm.size()}")
    results = vm.search("航班", top_k=3)
    print(f"  搜索'航班': {[e.content[:15] for e, _ in results] if results else '无结果'}")

    # 清理
    vm.clear()

    print("\n" + "=" * 60)
    print("Demo 4 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
