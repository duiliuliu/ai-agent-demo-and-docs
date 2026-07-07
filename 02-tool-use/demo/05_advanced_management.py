from sys import path
path.append('/workspace/02-tool-use')

from skill import (
    tool_registry,
    skill_manager,
    prompt_manager,
    router
)


def get_weather(city: str) -> str:
    return f"天气模拟：{city} 晴朗，28°C"


def search_flight(departure: str, destination: str, date: str) -> str:
    return f"航班模拟：{date} {departure}->{destination} 有3个航班可选"


def send_email(to: str, subject: str, body: str) -> str:
    return f"邮件模拟：已发送给 {to}，主题: {subject}"


class WeatherSkill:
    def process(self, city: str) -> str:
        return f"WeatherSkill处理: {city}"


class FlightSkill:
    def process(self, departure: str, destination: str, date: str) -> str:
        return f"FlightSkill处理: {departure}->{destination} {date}"


class EmailSkill:
    def process(self, to: str, subject: str, body: str) -> str:
        return f"EmailSkill处理: 发送给 {to}"


def print_separator(title):
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")


def main():
    print("=" * 60)
    print("Demo 5: 进阶管理功能")
    print("=" * 60)

    print_separator("1. 工具管理")
    print("注册工具:")
    tool_registry.register_tool("get_weather", get_weather, "查询天气")
    tool_registry.register_tool("search_flight", search_flight, "搜索航班")
    print(f"当前工具列表: {tool_registry.list_tools()}")

    print("\n查看工具元数据:")
    metadata = tool_registry.get_tool_metadata("get_weather")
    print(f"get_weather: {metadata.description}, 参数: {metadata.parameters}")

    print("\n卸载工具:")
    result = tool_registry.unregister_tool("search_flight")
    print(f"卸载 search_flight 成功: {result}")
    print(f"当前工具列表: {tool_registry.list_tools()}")

    print("\n重新注册工具:")
    tool_registry.register_tool("search_flight", search_flight, "搜索航班")
    tool_registry.register_tool("send_email", send_email, "发送邮件")
    print(f"当前工具列表: {tool_registry.list_tools()}")

    print_separator("2. Skill管理")
    print("注册Skill:")
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

    print(f"当前Skill列表: {skill_manager.list_skills()}")

    print("\n按意图查询Skill:")
    weather_skills = skill_manager.get_skills_by_intent("weather")
    print(f"支持weather意图的Skill: {weather_skills}")

    print("\n按工具查询Skill:")
    flight_tool_skills = skill_manager.get_skills_by_tool("search_flight")
    print(f"使用search_flight工具的Skill: {flight_tool_skills}")

    print("\n卸载Skill:")
    result = skill_manager.unregister_skill("weather_skill")
    print(f"卸载 weather_skill 成功: {result}")
    print(f"当前Skill列表: {skill_manager.list_skills()}")

    print("\n重新注册Skill:")
    skill_manager.register_skill(
        name="weather_skill",
        skill_instance=weather_skill,
        description="天气查询技能",
        required_tools=["get_weather"],
        supported_intents=["weather"]
    )

    email_skill = EmailSkill()
    skill_manager.register_skill(
        name="email_skill",
        skill_instance=email_skill,
        description="邮件发送技能",
        required_tools=["send_email"],
        supported_intents=["send_email"]
    )
    print(f"当前Skill列表: {skill_manager.list_skills()}")

    print_separator("3. Prompt管理")
    print("查看已注册的Prompt:")
    print(f"当前Prompt列表: {prompt_manager.list_prompts()}")

    print("\n注册新Prompt:")
    SUMMARIZE_PROMPT = """
你是一个总结助手。请将以下对话内容进行简洁总结：

对话内容：
{conversation}

总结要求：
1. 突出关键点
2. 保持在100字以内
3. 使用自然流畅的语言

总结结果：
"""

    prompt_manager.register_prompt(
        name="summarize",
        template=SUMMARIZE_PROMPT,
        description="对话总结Prompt",
        required_vars=["conversation"]
    )
    print(f"当前Prompt列表: {prompt_manager.list_prompts()}")

    print("\n渲染Prompt:")
    rendered = prompt_manager.render_prompt("summarize", conversation="用户：你好，帮我查天气。助理：好的，请问哪个城市？")
    print(f"渲染结果:\n{rendered}")

    print("\n卸载Prompt:")
    result = prompt_manager.unregister_prompt("summarize")
    print(f"卸载 summarize 成功: {result}")
    print(f"当前Prompt列表: {prompt_manager.list_prompts()}")

    print_separator("4. 路由管理")
    print("注册路由:")
    router.register_route("weather", "weather_skill", "intent_recognition", ["get_weather"])
    router.register_route("book_flight", "flight_skill", "intent_recognition", ["search_flight"])
    print(f"当前路由: {router.get_routes()}")

    print("\n验证路由:")
    route = router.get_route("weather")
    validation = router.validate_route(route)
    print(f"weather路由验证: valid={validation['valid']}, errors={validation['errors']}, warnings={validation['warnings']}")

    print("\n卸载路由:")
    result = router.unregister_route("book_flight")
    print(f"卸载 book_flight 路由成功: {result}")
    print(f"当前路由: {router.get_routes()}")

    print("\n" + "=" * 60)
    print("Demo 5 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()