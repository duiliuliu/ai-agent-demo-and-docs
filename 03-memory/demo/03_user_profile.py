"""Demo 3: 用户画像

演示：
- 基本信息、偏好、关联实体、标签
- 历史记录分类管理
- 生成结构化画像上下文
- Token 估算
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import UserProfile


def main():
    print("=" * 60)
    print("Demo 3: 用户画像")
    print("=" * 60)

    profile = UserProfile("demo_user", storage_path=os.path.join(os.path.dirname(__file__), "..", "data", "demo03_profile.json"))
    profile.clear()

    print("\n[1] 设置基本信息")
    profile.set_basic_info("姓名", "张三")
    profile.set_basic_info("年龄", 30)
    profile.set_basic_info("城市", "北京")

    print("[2] 设置偏好")
    profile.set_preference("语言", "中文")
    profile.set_preference("主题", "深色")
    profile.set_preference("时区", "Asia/Shanghai")

    print("[3] 添加关联实体")
    profile.add_entity("常用地址", "北京市朝阳区xx街道")
    profile.add_entity("邮箱", "zhangsan@example.com")

    print("[4] 添加标签")
    profile.add_tag("旅游爱好者")
    profile.add_tag("美食家")
    profile.add_tag("AI技术")

    print("[5] 添加历史记录")
    profile.add_history_item("查询了北京天气", "weather")
    profile.add_history_item("预订了北京到上海机票", "flight")
    profile.add_history_item("搜索了AI最新资讯", "search")

    print("\n[6] 读取画像数据")
    print(f"  姓名: {profile.get_basic_info('姓名')}")
    print(f"  城市: {profile.get_basic_info('城市')}")
    print(f"  语言偏好: {profile.get_preference('语言')}")
    print(f"  邮箱: {profile.get_entity('邮箱')}")

    print(f"\n[7] 分类历史查询")
    for cat in ["weather", "flight", "search"]:
        items = profile.get_history(cat)
        print(f"  {cat}: {len(items)}条 - {items[0]['content'] if items else '无'}")

    print(f"\n[8] 生成上下文（注入Prompt用）")
    ctx = profile.to_context()
    print(f"  {ctx}")
    print(f"  Token 估算: {profile.estimate_tokens()}")

    # 清理
    profile.clear()

    print("\n" + "=" * 60)
    print("Demo 3 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
