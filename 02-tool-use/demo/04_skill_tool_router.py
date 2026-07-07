from sys import path
path.append('/workspace/02-tool-use')

from skill import (
    tool_registry,
    tool_executor,
    skill_manager,
    intent_recognizer,
    router
)


def get_weather(city: str) -> str:
    weather_data = {
        "北京": {"temperature": 28, "condition": "晴朗", "wind": "微风"},
        "上海": {"temperature": 32, "condition": "多云", "wind": "东风3级"},
        "广州": {"temperature": 35, "condition": "雷阵雨", "wind": "南风2级"},
        "深圳": {"temperature": 34, "condition": "多云转晴", "wind": "东北风"},
        "杭州": {"temperature": 30, "condition": "阴天", "wind": "西北风"},
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


def get_help(topic: str = "") -> str:
    if topic:
        return f"关于'{topic}'的帮助信息：这是一个演示系统，支持天气查询、航班预订等功能。"
    return "欢迎使用智能助手！我可以帮您查询天气、预订机票、搜索信息等。请问需要什么帮助？"


class WeatherSkill:
    def __init__(self):
        self.name = "weather_skill"

    def process(self, city: str) -> str:
        print(f"[Skill执行] WeatherSkill.process(city='{city}')")
        result = tool_executor.execute("get_weather", city=city)
        if result.success:
            return f"天气查询结果：\n{result.result}"
        return f"天气查询失败：{result.error}"


class FlightSkill:
    def __init__(self):
        self.name = "flight_skill"

    def process(self, departure: str, destination: str, date: str) -> str:
        print(f"[Skill执行] FlightSkill.process(departure='{departure}', destination='{destination}', date='{date}')")
        result = tool_executor.execute("search_flight", departure=departure, destination=destination, date=date)
        if result.success:
            return f"航班查询结果：\n{result.result}"
        return f"航班查询失败：{result.error}"


def main():
    print("=" * 60)
    print("Demo 4: Skill和工具路由")
    print("=" * 60)

    print("\n1. 注册工具")
    tool_registry.register_tool("get_weather", get_weather, "查询天气")
    tool_registry.register_tool("search_flight", search_flight, "搜索航班")
    tool_registry.register_tool("get_help", get_help, "获取帮助")

    print(f"已注册工具: {tool_registry.list_tools()}")

    print("\n2. 注册Skill")
    weather_skill = WeatherSkill()
    flight_skill = FlightSkill()

    skill_manager.register_skill(
        name="weather_skill",
        skill_instance=weather_skill,
        description="天气查询技能",
        required_tools=["get_weather"],
        supported_intents=["weather"]
    )

    skill_manager.register_skill(
        name="flight_skill",
        skill_instance=flight_skill,
        description="航班预订技能",
        required_tools=["search_flight"],
        supported_intents=["book_flight"]
    )

    print(f"已注册Skill: {skill_manager.list_skills()}")

    print("\n3. 配置路由")
    router.register_route(
        intent="weather",
        skill_name="weather_skill",
        prompt_name="intent_recognition",
        tool_names=["get_weather"]
    )

    router.register_route(
        intent="book_flight",
        skill_name="flight_skill",
        prompt_name="intent_recognition",
        tool_names=["search_flight"]
    )

    print(f"已配置路由: {router.get_routes()}")

    print("\n4. 完整流程演示")
    available_skills = ["weather", "book_flight", "search", "settings", "help", "general_chat"]

    test_cases = [
        "查一下北京的天气",
        "明天北京到上海的航班",
        "帮我订一张下周五去杭州的机票",
    ]

    for user_input in test_cases:
        print(f"\n{'='*50}")
        print(f"用户输入: {user_input}")
        print(f"{'='*50}")

        analysis = intent_recognizer.recognize(user_input, [], available_skills)
        print(f"意图识别结果: {analysis.intent.get('primary')}")
        print(f"可执行: {analysis.execution.get('can_proceed')}")

        if analysis.execution.get("can_proceed"):
            route = router.route(analysis)
            print(f"路由选择: skill={route.skill_name}, tools={route.tool_names}, confidence={route.confidence}")

            if route.skill_name and skill_manager.has_skill(route.skill_name):
                skill_instance, _ = skill_manager.get_skill(route.skill_name)

                slots = analysis.provided_info.get("slots", {})
                if route.skill_name == "weather_skill":
                    result = skill_instance.process(city=slots.get("city"))
                elif route.skill_name == "flight_skill":
                    result = skill_instance.process(
                        departure=slots.get("departure_city"),
                        destination=slots.get("destination"),
                        date=slots.get("departure_date")
                    )
                else:
                    result = "未知技能"

                print(f"最终结果:\n{result}")
            else:
                print("未找到匹配的Skill")
        else:
            print(f"需要追问: {analysis.execution.get('suggested_response')}")

    print("\n" + "=" * 60)
    print("Demo 4 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()