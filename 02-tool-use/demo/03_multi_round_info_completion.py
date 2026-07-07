from sys import path
path.append('/workspace/02-tool-use')

from skill import intent_recognizer, tool_executor, tool_registry
import json


def get_weather(city: str) -> str:
    weather_data = {
        "北京": {"temperature": 28, "condition": "晴朗", "wind": "微风"},
        "上海": {"temperature": 32, "condition": "多云", "wind": "东风3级"},
        "广州": {"temperature": 35, "condition": "雷阵雨", "wind": "南风2级"},
        "深圳": {"temperature": 34, "condition": "多云转晴", "wind": "东北风"},
        "杭州": {"temperature": 30, "condition": "阴天", "wind": "西北风"},
        "成都": {"temperature": 26, "condition": "小雨", "wind": "北风"},
        "重庆": {"temperature": 31, "condition": "多云", "wind": "东南风"},
    }
    data = weather_data.get(city, {"temperature": 25, "condition": "未知", "wind": "未知"})
    return f"{city}的天气：{data['condition']}，温度{data['temperature']}°C，{data['wind']}"


def search_flight(departure: str, destination: str, date: str) -> str:
    flights = [
        {"airline": "国航", "flight_no": "CA1234", "time": "08:30", "price": 800},
        {"airline": "东航", "flight_no": "MU5678", "time": "10:15", "price": 950},
        {"airline": "南航", "flight_no": "CZ9012", "time": "14:00", "price": 780},
    ]
    result = f"{date}从{departure}到{destination}的航班信息：\n"
    for flight in flights:
        result += f"- {flight['airline']} {flight['flight_no']} {flight['time']} 起飞，价格¥{flight['price']}\n"
    return result.strip()


def print_conversation(history):
    print("\n对话历史:")
    for msg in history:
        role = "用户" if msg["role"] == "user" else "助理"
        print(f"  {role}: {msg['content']}")


def simulate_multi_round_conversation(user_inputs):
    print("=" * 60)
    print("模拟多轮对话")
    print("=" * 60)

    available_skills = ["weather", "book_flight", "search", "settings", "help", "general_chat"]
    conversation_history = []
    accumulated_slots = {}

    for round_num, user_input in enumerate(user_inputs, 1):
        print(f"\n{'='*50}")
        print(f"第 {round_num} 轮")
        print(f"{'='*50}")
        print(f"用户输入: {user_input}")

        conversation_history.append({"role": "user", "content": user_input})

        analysis = intent_recognizer.recognize(
            user_message=user_input,
            conversation_history=conversation_history,
            available_skills=available_skills
        )

        for slot, value in analysis.provided_info.get("slots", {}).items():
            accumulated_slots[slot] = value

        print(f"累计槽位: {json.dumps(accumulated_slots, ensure_ascii=False)}")
        print(f"缺失参数: {analysis.missing_info.get('required')}")
        print(f"可执行: {analysis.execution.get('can_proceed')}")
        print(f"下一步动作: {analysis.execution.get('next_action')}")

        if analysis.execution.get("can_proceed"):
            assistant_response = analysis.execution.get("suggested_response", "")
            
            primary_intent = analysis.intent.get("primary")
            if primary_intent == "weather":
                result = tool_executor.execute("get_weather", city=accumulated_slots.get("city"))
                assistant_response = result.result if result.success else f"查询失败: {result.error}"
            elif primary_intent == "book_flight":
                result = tool_executor.execute(
                    "search_flight",
                    departure=accumulated_slots.get("departure_city"),
                    destination=accumulated_slots.get("destination"),
                    date=accumulated_slots.get("departure_date")
                )
                assistant_response = result.result if result.success else f"查询失败: {result.error}"

            print(f"助理回复: {assistant_response}")
            conversation_history.append({"role": "assistant", "content": assistant_response})
            break
        else:
            assistant_response = analysis.execution.get("suggested_response", "我需要更多信息。")
            print(f"助理回复: {assistant_response}")
            conversation_history.append({"role": "assistant", "content": assistant_response})

    print_conversation(conversation_history)


def main():
    print("=" * 60)
    print("Demo 3: 多轮信息补全")
    print("=" * 60)

    tool_registry.register_tool(
        name="get_weather",
        func=get_weather,
        description="查询指定城市的天气信息",
        parameters={"city": {"type": "str", "required": True, "description": "城市名称"}}
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

    print("\n场景1: 查询天气（需要补充城市）")
    simulate_multi_round_conversation([
        "查一下天气",
        "北京"
    ])

    print("\n" + "=" * 60)
    print("场景2: 预订机票（需要补充出发城市和日期）")
    simulate_multi_round_conversation([
        "帮我订一张去杭州的机票",
        "从上海出发",
        "下周五"
    ])

    print("\n" + "=" * 60)
    print("场景3: 查询航班（信息完整，直接执行）")
    simulate_multi_round_conversation([
        "明天北京到上海的航班"
    ])

    print("\n" + "=" * 60)
    print("Demo 3 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()