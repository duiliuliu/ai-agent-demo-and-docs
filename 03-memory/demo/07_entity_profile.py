"""Demo 7: 泛化实体画像 - 用户/项目/产品/其他

演示 EntityProfile 如何统一处理不同主体的画像：
- 用户画像：姓名、年龄、饮食偏好
- 项目画像：项目名、预算、周期、关联用户、状态
- 产品画像：产品名、价格、特性、状态
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import EntityProfile


def main():
    print("=" * 60)
    print("Demo 7: 泛化实体画像（用户/项目/产品）")
    print("=" * 60)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")

    # ---- 用户画像 ----
    print("\n[1] 用户画像（user 类型）")
    user = EntityProfile("zhangsan", "user", storage_path=os.path.join(data_dir, "demo07_user.json"))
    user.clear()
    user.set_basic_info("姓名", "张三")
    user.set_basic_info("年龄", 30)
    user.set_preference("饮食", "川菜")
    user.set_preference("时区", "Asia/Shanghai")
    user.add_tag("VIP")
    user.add_tag("旅游爱好者")
    print(user.to_context())

    # ---- 项目画像 ----
    print("\n[2] 项目画像（project 类型）")
    project = EntityProfile("proj_001", "project", storage_path=os.path.join(data_dir, "demo07_project.json"))
    project.clear()
    project.set_basic_info("项目名", "AI助手开发")
    project.set_basic_info("负责人", "李四")
    project.set_attribute("预算", "50万")
    project.set_attribute("周期", "6个月")
    # 状态（支持过期）
    project.set_state("当前阶段", "开发中", ttl_seconds=None)
    project.set_state("紧急任务", "完成MVP", ttl_seconds=7*24*3600)  # 7天过期
    # 关联关系
    project.add_relation("zhangsan", "产品经理")
    project.add_relation("user_lisi", "开发负责人")
    project.add_tag("高优先级")
    print(project.to_context())

    # ---- 产品画像 ----
    print("\n[3] 产品画像（product 类型）")
    product = EntityProfile("prod_X", "product", storage_path=os.path.join(data_dir, "demo07_product.json"))
    product.clear()
    product.set_basic_info("产品名", "智能客服系统")
    product.set_basic_info("版本", "v2.0")
    product.set_attribute("价格", "9999元/月")
    product.set_attribute("目标用户", "中小企业")
    product.set_state("状态", "已发布")
    product.set_state("在线用户数", 1500)
    print(product.to_context())

    # ---- 状态过期演示 ----
    print("\n[4] 状态过期演示（修改 TTL 为 2 秒后观察）")
    proj_temp = EntityProfile("proj_temp", "project", storage_path=os.path.join(data_dir, "demo07_proj_temp.json"))
    proj_temp.clear()
    proj_temp.set_state("临时状态", "测试中", ttl_seconds=2)
    print(f"  设置后: {proj_temp.get_state('临时状态')}")
    import time
    time.sleep(3)
    print(f"  3秒后: {proj_temp.get_state('临时状态', '已过期')}")

    # ---- 关联查询 ----
    print("\n[5] 关联关系查询")
    rels = project.get_relations()
    print(f"  项目的所有关联实体:")
    for entity_id, relations in rels.items():
        for r in relations:
            print(f"    {entity_id} - {r['relation']}")

    # 清理
    user.clear()
    project.clear()
    product.clear()
    proj_temp.clear()

    print("\n" + "=" * 60)
    print("Demo 7 完成")
    print("=" * 60)
    print("""
    核心要点：
    - EntityProfile 是泛化的主体画像，user/project/product/team/scene 都用它
    - attributes（属性）替代了硬编码的"基本信息"，更通用
    - relations（关联）表达实体间关系
    - states（状态）支持 TTL 自动过期
    - 不同的 entity_type 渲染不同的 to_context() 格式
    """)


if __name__ == "__main__":
    main()
