"""Demo 2: ReAct (Reasoning + Acting) 推理

演示：
- 工具注册与调用
- Thought → Action → Observation 循环
- 多步推理
- 死循环检测
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import ReActReasoner, ToolRegistry


# 模拟工具实现
def get_weather(params: dict) -> str:
    """查询天气"""
    city = params.get("city", "未知")
    weather_data = {
        "北京": "北京今天28度，晴",
        "上海": "上海今天32度，晴",
        "广州": "广州今天30度，多云",
        "深圳": "深圳今天31度，多云",
        "杭州": "杭州今天26度，阴"
    }
    return weather_data.get(city, f"{city}今天25度")


def calculator(params: dict) -> str:
    """计算器"""
    expr = params.get("expression", "")
    try:
        # 简单的表达式求值（仅支持 + - × ÷）
        expr = expr.replace("×", "*").replace("÷", "/").replace("x", "*")
        result = eval(expr)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"


def search(params: dict) -> str:
    """搜索"""
    query = params.get("query", "")
    return f"关于'{query}'的搜索结果：这是相关的模拟信息"


def main():
    print("=" * 60)
    print("Demo 2: ReAct (Reasoning + Acting) 推理")
    print("=" * 60)

    # 创建推理器并注册工具
    reasoner = ReActReasoner(max_steps=6)
    reasoner.register_tool("get_weather", get_weather, "查询指定城市的天气")
    reasoner.register_tool("calculator", calculator, "执行数学计算")
    reasoner.register_tool("search", search, "搜索信息")

    print("\n[案例 1] 单城市天气查询（1轮工具调用）")
    result = reasoner.reason("北京今天天气怎么样？")
    print(result.trace())

    print("\n[案例 2] 多城市天气比较（2轮工具调用）")
    result = reasoner.reason("北京和上海今天哪个城市更暖和？")
    print(result.trace())

    print("\n[案例 3] 数学计算（1轮工具调用）")
    result = reasoner.reason("12乘以8再加5等于多少？")
    print(result.trace())

    print("\n[案例 4] 搜索 + 计算的组合（多轮工具调用）")
    result = reasoner.reason("搜索Python的发布时间，然后计算Python 3.0距离现在多少年？")
    print(result.trace())

    print("\n[案例 5] 死循环检测")
    print("  说明：如果连续3步调用相同工具，推理会强制终止")
    result = reasoner.reason("循环执行 get_weather 工具")
    # 模拟一个会陷入循环的问题（实际LLM一般不会，但演示机制）
    if "loop_detected" in (result.error or ""):
        print(f"  ✓ 死循环被检测到，推理终止")
        print(f"  最终结果: {result.final_answer}")

    print("\n" + "=" * 60)
    print("Demo 2 完成")
    print("=" * 60)
    print("""
    ReAct 适用场景：
    - 需要查询实时信息（天气、股票、新闻）
    - 需要调用工具（计算器、搜索、数据库）
    - 多步交互任务

    成本：N 次 LLM 调用 + N 次工具调用
    """)


if __name__ == "__main__":
    main()
