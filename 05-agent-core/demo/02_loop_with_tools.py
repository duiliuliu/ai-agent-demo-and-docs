"""
Demo 02: 带工具调用的 Agent 循环

场景：展示如何在 Agent 循环中集成工具调用
目标：理解工具调用在循环中的作用和流程

核心知识点：
  1. 工具注册和调用机制
  2. 工具调用结果如何反馈到循环中
  3. 如何处理工具调用的返回值
  4. 工具调用的统计和监控

运行方式：
  python demo/02_loop_with_tools.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill.agent_loop import AgentLoop


class MockToolRegistry:
    def __init__(self):
        self._tools = {
            "search_weather": self._search_weather,
            "search_flight": self._search_flight,
            "calculate": self._calculate
        }

    def call(self, tool_name: str, args: dict) -> str:
        if tool_name in self._tools:
            return self._tools[tool_name](**args)
        return f"未知工具: {tool_name}"

    def _search_weather(self, city: str = "北京") -> str:
        weather_data = {
            "北京": {"temperature": "25°C", "condition": "晴朗", "wind": "微风"},
            "上海": {"temperature": "28°C", "condition": "多云", "wind": "东北风"},
            "广州": {"temperature": "32°C", "condition": "小雨", "wind": "南风"}
        }
        info = weather_data.get(city, {"temperature": "未知", "condition": "未知", "wind": "未知"})
        return f"{city}天气：{info['condition']}，温度{info['temperature']}，{info['wind']}"

    def _search_flight(self, from_city: str, to_city: str) -> str:
        return f"从{from_city}到{to_city}的航班信息：CA1234，明天上午10:00起飞，票价500元"

    def _calculate(self, expression: str) -> str:
        try:
            result = eval(expression)
            return f"计算结果: {expression} = {result}"
        except Exception:
            return f"计算失败: {expression}"


def demo_loop_with_tools():
    print("=" * 60)
    print("Demo 02: 带工具调用的 Agent 循环")
    print("=" * 60)
    print()

    tool_registry = MockToolRegistry()

    loop = AgentLoop(
        tool_registry=tool_registry,
        max_steps=4
    )

    user_input = "查询北京的天气，然后计算 100 + 200"

    print(f"用户输入: {user_input}")
    print(f"可用工具: {list(tool_registry._tools.keys())}")
    print()

    result = loop.run(user_input)

    print("-" * 60)
    print("执行结果:")
    print("-" * 60)
    print(result.trace())
    print()

    print("=" * 60)
    print("工具调用机制解析")
    print("=" * 60)
    print("""
1. 工具注册（Tool Registry）：
   - 将工具函数注册到一个统一的注册表中
   - 本示例注册了三个工具：search_weather、search_flight、calculate

2. 工具调用流程：
   - Thought 阶段：推理引擎决定需要调用工具
   - Action 阶段：AgentLoop 调用 tool_registry.call(tool_name, args)
   - Observation 阶段：工具返回结果被作为下一步的观察输入

3. 工具调用统计：
   - total_tool_calls: 工具调用总次数
   - 每步都会记录是否调用了工具

4. 实际应用场景：
   - 搜索工具：查询外部信息
   - API 工具：调用第三方服务
   - 数据库工具：查询数据库
   - 文件工具：读写文件

关键设计原则：
  - 工具应该是无状态的（Stateless）
  - 工具调用应该是幂等的（Idempotent）
  - 工具返回值应该是可序列化的
  - 工具应该有明确的输入输出规范
""")


if __name__ == "__main__":
    demo_loop_with_tools()
