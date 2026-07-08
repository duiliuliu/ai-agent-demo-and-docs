"""Demo 5: 意图识别驱动的推理路由（进阶）

演示：
- ReasoningRouter 自动选择推理方式
- 与 02-tool-use 的 IntentRecognizer 集成
- 不同输入触发不同推理策略
- 工具注册器统一管理
- 一站式推理入口
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import ReasoningRouter, ToolRegistry, ReasoningType


# 工具实现
def get_weather(params):
    city = params.get("city", "")
    data = {
        "北京": "北京28度，晴，西北风3级",
        "上海": "上海32度，晴，东南风2级",
        "广州": "广州30度，多云",
        "深圳": "深圳31度，多云",
        "杭州": "杭州26度，阴，有小雨"
    }
    return data.get(city, f"{city} 25度")


def search(params):
    query = params.get("query", "")
    return f"搜索'{query}'的模拟结果：相关文档 3 篇，关键信息已提取"


def calculator(params):
    expr = params.get("expression", "").replace("×", "*").replace("÷", "/")
    try:
        return str(eval(expr))
    except Exception as e:
        return f"错误: {e}"


def main():
    print("=" * 60)
    print("Demo 5: 意图识别驱动的推理路由")
    print("=" * 60)

    # 创建路由 + 注册工具
    router = ReasoningRouter()
    router.register_tool("get_weather", get_weather, "查询指定城市天气")
    router.register_tool("search", search, "搜索信息")
    router.register_tool("calculator", calculator, "数学计算")

    # 模拟意图识别结果（来自 02-tool-use）
    test_cases = [
        # (用户输入, 意图识别结果)
        ("你好", "greeting"),                                    # → NONE
        ("谢谢", "thanks"),                                       # → NONE
        ("3 + 5 等于多少？", "math"),                            # → CoT
        ("为什么天空是蓝色的？", "qa"),                         # → CoT
        ("北京今天天气怎么样？", "weather_query"),               # → ReAct
        ("北京和上海哪个更热？", "weather_query"),                # → ReAct (多步)
        ("100乘以5等于多少？", "calculation"),                   # → ReAct (用工具)
        ("搜索Python教程", "search"),                            # → ReAct
        ("帮我规划一个3天杭州旅行", "travel_plan"),              # → Plan-and-Solve
        ("研究对比Python和Go的优劣", "research"),                # → Plan-and-Solve
    ]

    total_llm_calls = 0
    total_tool_calls = 0

    for user_input, intent in test_cases:
        print(f"\n{'─' * 50}")
        print(f"  输入: '{user_input}' | 意图: {intent}")
        print(f"{'─' * 50}")

        # 1. 路由决策
        reasoning_type = router.decide_reasoning_type(user_input, intent)
        type_names = {
            ReasoningType.NONE: "无推理（直接回答）",
            ReasoningType.COT: "CoT (思维链)",
            ReasoningType.REACT: "ReAct (思考+行动)",
            ReasoningType.PLAN_AND_SOLVE: "Plan-and-Solve"
        }
        print(f"  → 路由决策: {type_names[reasoning_type]}")

        # 2. 执行推理
        result = router.reason(user_input, intent=intent)
        total_llm_calls += result.total_llm_calls
        total_tool_calls += result.total_tool_calls

        print(f"  步数: {len(result.steps)}, LLM调用: {result.total_llm_calls}, 工具调用: {result.total_tool_calls}")
        print(f"  耗时: {result.execution_time_ms:.1f}ms")
        print(f"  答案: {result.final_answer[:80] if result.final_answer else '无'}")

    # 总结
    print(f"\n{'═' * 60}")
    print("[统计]")
    print(f"{'═' * 60}")
    print(f"  总输入数: {len(test_cases)}")
    print(f"  总 LLM 调用: {total_llm_calls}")
    print(f"  总工具调用: {total_tool_calls}")
    print(f"  平均每次输入 LLM 调用: {total_llm_calls / len(test_cases):.1f}")

    # 路由规则
    print(f"\n{'═' * 60}")
    print("[路由规则总结]")
    print(f"{'═' * 60}")
    print("""
    ┌────────────────┬──────────────────┬──────────────┐
    │ 意图类型        │ 推理方式          │ 典型场景      │
    ├────────────────┼──────────────────┼──────────────┤
    │ greeting       │ NONE             │ 打招呼        │
    │ thanks         │ NONE             │ 致谢          │
    │ qa / math      │ CoT              │ 简单问答      │
    │ weather_query  │ ReAct            │ 实时信息查询  │
    │ search         │ ReAct            │ 信息检索      │
    │ calculation    │ ReAct            │ 工具计算      │
    │ travel_plan    │ Plan-and-Solve   │ 复杂规划      │
    │ research       │ Plan-and-Solve   │ 研究分析      │
    └────────────────┴──────────────────┴──────────────┘

    核心价值：
    - 简单任务用 CoT/NONE（1次LLM调用，省钱）
    - 需要工具的任务用 ReAct（按需调用）
    - 复杂任务用 Plan-and-Solve（提前规划）

    与 02-tool-use 联动：
    - IntentRecognizer 输出 intent
    - ReasoningRouter 接收 intent 选择推理方式
    - ToolRegistry 统一管理所有工具
    """)

    print("\n" + "=" * 60)
    print("Demo 5 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
