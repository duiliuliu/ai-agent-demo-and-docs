"""Demo 1: CoT (Chain of Thought) 推理

演示：
- 单轮推理
- 思维链分步思考
- 数学题、逻辑题、解释类问题的处理
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import CoTReasoner


def main():
    print("=" * 60)
    print("Demo 1: CoT (Chain of Thought) 推理")
    print("=" * 60)

    reasoner = CoTReasoner()

    # 案例1：数学题
    print("\n[案例 1] 数学题")
    question = "一个苹果5元，三个苹果多少钱？"
    result = reasoner.reason(question)
    print(result.trace())
    print(f"  最终答案: {result.final_answer}")

    # 案例2：复杂计算
    print("\n[案例 2] 复杂计算")
    question = "12 × 8 + 5 等于多少？"
    result = reasoner.reason(question)
    print(result.trace())
    print(f"  最终答案: {result.final_answer}")

    # 案例3：解释类
    print("\n[案例 3] 解释类问题")
    question = "为什么天空是蓝色的？"
    result = reasoner.reason(question)
    print(result.trace())
    print(f"  最终答案: {result.final_answer}")

    print("\n" + "=" * 60)
    print("Demo 1 完成")
    print("=" * 60)
    print("""
    CoT 适用场景：
    - 数学题、逻辑推理
    - 简单分析任务
    - 不需要外部信息的推理

    成本：1 次 LLM 调用
    """)


if __name__ == "__main__":
    main()
