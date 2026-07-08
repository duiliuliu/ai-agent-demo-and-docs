"""Demo 3: Plan-and-Solve 推理

演示：
- 阶段1: 规划（生成执行计划）
- 阶段2: 求解（逐步执行）
- 阶段3: 验证（验证结果并给出最终答案）
- 不同类型任务的规划
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import PlanAndSolveReasoner


def main():
    print("=" * 60)
    print("Demo 3: Plan-and-Solve 推理")
    print("=" * 60)

    reasoner = PlanAndSolveReasoner(max_steps=10)

    # 案例1：旅行规划
    print("\n[案例 1] 旅行规划（多步任务）")
    question = "帮我规划一个3天的杭州旅行，包括景点、住宿和预算"
    result = reasoner.reason(question)
    print(result.trace())

    # 案例2：研究类问题
    print("\n[案例 2] 技术研究对比")
    question = "对比分析Python和Go语言在后端开发中的优劣势"
    result = reasoner.reason(question)
    print(result.trace())

    # 案例3：计算类
    print("\n[案例 3] 多步计算")
    question = "如果每月存1000元，年化收益5%，10年后总共多少钱？"
    result = reasoner.reason(question)
    print(result.trace())

    print("\n" + "=" * 60)
    print("Demo 3 完成")
    print("=" * 60)
    print("""
    Plan-and-Solve 适用场景：
    - 复杂多步任务
    - 任务需要提前规划
    - 用户希望审核执行计划
    - 任务执行顺序有依赖关系

    成本：1 规划 + N 求解 + 1 验证 = N+2 次 LLM 调用
    """)


if __name__ == "__main__":
    main()
