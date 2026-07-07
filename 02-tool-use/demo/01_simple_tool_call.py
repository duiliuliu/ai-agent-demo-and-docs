import os
from sys import path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import tool_registry, tool_executor


def get_weather(city: str) -> str:
    print(f"[工具调用] get_weather(city='{city}')")
    weather_data = {
        "北京": {"temperature": 28, "condition": "晴朗", "wind": "微风"},
        "上海": {"temperature": 32, "condition": "多云", "wind": "东风3级"},
        "广州": {"temperature": 35, "condition": "雷阵雨", "wind": "南风2级"},
        "深圳": {"temperature": 34, "condition": "多云转晴", "wind": "东北风"},
        "杭州": {"temperature": 30, "condition": "阴天", "wind": "西北风"},
    }
    data = weather_data.get(city, {"temperature": 25, "condition": "未知", "wind": "未知"})
    result = f"{city}的天气：{data['condition']}，温度{data['temperature']}°C，{data['wind']}"
    print(f"[工具返回] {result}")
    return result


def search_flight(departure: str, destination: str, date: str) -> str:
    print(f"[工具调用] search_flight(departure='{departure}', destination='{destination}', date='{date}')")
    flights = [
        {"airline": "国航", "flight_no": "CA1234", "time": "08:30", "price": 800},
        {"airline": "东航", "flight_no": "MU5678", "time": "10:15", "price": 950},
        {"airline": "南航", "flight_no": "CZ9012", "time": "14:00", "price": 780},
    ]
    result = f"{date}从{departure}到{destination}的航班信息：\n"
    for flight in flights:
        result += f"- {flight['airline']} {flight['flight_no']} {flight['time']} 起飞，价格¥{flight['price']}\n"
    print(f"[工具返回] {result}")
    return result.strip()


def main():
    print("=" * 60)
    print("Demo 1: 简单工具调用")
    print("=" * 60)

    print("\n1. 注册工具")
    tool_registry.register_tool(
        name="get_weather",
        func=get_weather,
        description="查询指定城市的天气信息",
        parameters={
            "city": {"type": "str", "required": True, "description": "城市名称"}
        }
    )

    tool_registry.register_tool(
        name="search_flight",
        func=search_flight,
        description="搜索航班信息",
        parameters={
            "departure": {"type": "str", "required": True, "description": "出发城市"},
            "destination": {"type": "str", "required": True, "description": "目的城市"},
            "date": {"type": "str", "required": True, "description": "出发日期"}
        }
    )

    print(f"已注册工具: {tool_registry.list_tools()}")

    print("\n2. 执行工具调用")
    result1 = tool_executor.execute("get_weather", city="北京")
    print(f"\n执行结果1:")
    print(f"  成功: {result1.success}")
    print(f"  结果: {result1.result}")

    result2 = tool_executor.execute("search_flight", departure="北京", destination="上海", date="2026-07-10")
    print(f"\n执行结果2:")
    print(f"  成功: {result2.success}")
    print(f"  结果:\n{result2.result}")

    print("\n3. 执行失败案例（缺少参数）")
    result3 = tool_executor.execute("get_weather")
    print(f"执行结果3:")
    print(f"  成功: {result3.success}")
    print(f"  错误: {result3.error}")

    print("\n" + "=" * 60)
    print("Demo 1 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()