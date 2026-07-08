"""Demo 4: 多轮会话中的推理

演示：
- 多轮对话中保持推理状态
- 上一轮结果作为下一轮上下文
- 混合使用不同的推理方式
- 信息补全 + 推理结合
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import CoTReasoner, ReActReasoner, PlanAndSolveReasoner, ToolRegistry


# 工具实现
def get_weather(params):
    city = params.get("city", "未知")
    data = {"北京": "北京28度，晴", "上海": "上海32度，晴", "杭州": "杭州26度，阴"}
    return data.get(city, f"{city}25度")


def calculator(params):
    expr = params.get("expression", "").replace("×", "*").replace("÷", "/")
    try:
        return str(eval(expr))
    except Exception as e:
        return f"错误: {e}"


def main():
    print("=" * 60)
    print("Demo 4: 多轮会话中的推理")
    print("=" * 60)

    # 创建推理器
    cot = CoTReasoner()
    react = ReActReasoner(max_steps=6)
    react.register_tool("get_weather", get_weather, "查询天气")
    react.register_tool("calculator", calculator, "数学计算")
    plan = PlanAndSolveReasoner()

    conversation = [
        ("user", "我想算一下100乘以3", "math"),
        ("user", "北京今天热不热？", "weather_query"),
        ("user", "如果每天存30元，存一个月能存多少？", "calculation"),
        ("user", "帮我规划一下周末的杭州旅游", "travel_plan"),
    ]

    for round_num, (role, message, intent) in enumerate(conversation, 1):
        print(f"\n{'─' * 50}")
        print(f"  对话轮次 {round_num} | 意图: {intent}")
        print(f"  用户: {message}")
        print(f"{'─' * 50}")

        # 根据意图选择推理方式
        if intent == "math":
            result = cot.reason(message)
        elif intent == "weather_query":
            result = react.reason(message)
        elif intent == "calculation":
            result = cot.reason(message)
        elif intent == "travel_plan":
            result = plan.reason(message)
        else:
            result = cot.reason(message)

        print(f"\n  推理类型: {result.reasoning_type.value}")
        print(f"  步数: {len(result.steps)}")
        print(f"  LLM调用: {result.total_llm_calls} | 工具调用: {result.total_tool_calls}")
        print(f"  耗时: {result.execution_time_ms:.1f}ms")
        print(f"\n  最终答案: {result.final_answer}")

    # 总结
    print(f"\n{'═' * 50}")
    print("[会话总结]")
    print(f"{'═' * 50}")
    print("""
    关键观察：
    - 同一个会话中，Agent 根据不同意图使用不同推理方式
    - 这种"按需选择"的能力需要 ReasoningRouter 统一调度
    - 多轮会话的状态（上下文、记忆）会影响下一轮推理
    """)

    print("\n" + "=" * 60)
    print("Demo 4 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
