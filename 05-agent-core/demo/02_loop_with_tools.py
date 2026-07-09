"""
Demo 02: 带工具调用的 Agent 循环（ReAct 推理引擎）

场景：展示如何在 Agent 循环中集成工具调用（使用 ReAct 推理引擎）
目标：理解工具调用在循环中的作用和流程

核心知识点：
  1. 工具注册和调用机制
  2. ReAct 推理引擎的工作原理
  3. 工具调用结果如何反馈到循环中
  4. 如何处理工具调用的返回值

支持真实 LLM：
  设置环境变量即可使用真实 LLM + ReAct：
    export LLM_PROVIDER=openai
    export LLM_API_KEY=your-api-key
    export LLM_MODEL=gpt-3.5-turbo
    export REASONING_TYPE=react

运行方式：
  python demo/02_loop_with_tools.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_helper import create_agent_loop, print_config_info


class MockToolRegistry:
    """模拟工具注册表"""
    
    def __init__(self):
        self._tools = {
            "get_weather": self._get_weather,
            "get_flight": self._get_flight,
            "calculate": self._calculate,
            "get_exchange_rate": self._get_exchange_rate,
        }
        self._descriptions = {
            "get_weather": "查询指定城市的天气信息。参数：city（城市名，如'北京'）",
            "get_flight": "查询航班信息。参数：from_city（出发城市）, to_city（目的城市）",
            "calculate": "执行数学计算。参数：expression（数学表达式字符串，如'25+5'）",
            "get_exchange_rate": "查询汇率。参数：from_currency（源货币，如'USD'）, to_currency（目标货币，如'CNY'）",
        }

    def call(self, tool_name: str, args: dict) -> str:
        if tool_name in self._tools:
            return self._tools[tool_name](**args)
        return f"未知工具: {tool_name}"

    def _get_weather(self, city: str = "北京") -> str:
        weather_data = {
            "北京": {"temperature": 25, "condition": "晴朗", "wind": "微风", "humidity": 45},
            "上海": {"temperature": 28, "condition": "多云", "wind": "东北风3级", "humidity": 60},
            "广州": {"temperature": 32, "condition": "小雨", "wind": "南风2级", "humidity": 75},
            "深圳": {"temperature": 30, "condition": "晴", "wind": "微风", "humidity": 65},
            "成都": {"temperature": 22, "condition": "阴", "wind": "微风", "humidity": 55},
        }
        info = weather_data.get(city, {"temperature": "未知", "condition": "未知", "wind": "未知", "humidity": "未知"})
        return f"{city}天气：{info['condition']}，温度{info['temperature']}°C，{info['wind']}，湿度{info['humidity']}%"

    def _get_flight(self, from_city: str = "", to_city: str = "") -> str:
        flights = {
            ("北京", "上海"): "CA1234，08:00起飞，10:30到达，票价￥580",
            ("北京", "广州"): "CA5678，09:00起飞，12:00到达，票价￥850",
            ("上海", "北京"): "MU1234，14:00起飞，16:30到达，票价￥620",
            ("广州", "北京"): "CZ5678，15:00起飞，18:00到达，票价￥880",
        }
        key = (from_city, to_city)
        if key in flights:
            return f"从{from_city}到{to_city}的航班：{flights[key]}"
        return f"从{from_city}到{to_city}暂无航班信息"

    def _calculate(self, expression: str = "") -> str:
        try:
            # 安全计算（只允许基本数学运算）
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return f"计算失败：表达式包含非法字符"
            result = eval(expression)
            return f"计算结果: {expression} = {result}"
        except Exception as e:
            return f"计算失败: {expression}，错误: {e}"

    def _get_exchange_rate(self, from_currency: str = "USD", to_currency: str = "CNY") -> str:
        rates = {
            ("USD", "CNY"): 7.25,
            ("EUR", "CNY"): 7.85,
            ("CNY", "USD"): 0.14,
            ("CNY", "EUR"): 0.13,
        }
        key = (from_currency.upper(), to_currency.upper())
        if key in rates:
            return f"汇率：1 {from_currency} = {rates[key]} {to_currency}"
        return f"暂无 {from_currency} 到 {to_currency} 的汇率信息"


def demo_loop_with_tools():
    print_config_info()

    tool_registry = MockToolRegistry()

    loop = create_agent_loop(
        tool_registry=tool_registry,
        max_steps=10
    )

    # 复杂案例：需要多轮工具调用
    user_input = """
请帮我完成以下任务：
1. 查询北京和上海今天的天气
2. 比较两个城市哪个温度更高
3. 计算两个城市的温度差是多少
4. 查询从温度更高的城市到另一个城市的航班
"""

    print(f"用户输入: {user_input.strip()}")
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
   - 本示例注册了四个工具：get_weather、get_flight、calculate、get_exchange_rate

2. ReAct 推理流程：
   - Thought: 分析问题，决定需要调用哪个工具
   - Action: 指定工具名称和参数
   - Observation: 工具执行的结果（真实数据，不是编造）
   - 循环直到得到最终答案

3. 多轮调用的关键：
   - LLM 每次只输出一个 Thought + Action + Action Input
   - 系统执行工具，将 Observation 注入对话历史
   - LLM 根据真实数据继续推理下一步

4. 防止数据编造的机制：
   - Prompt 中明确要求"禁止编造 Observation"
   - 解析器只取第一个 Action，忽略 LLM 自编的后续内容
   - 强制要求先执行工具再继续推理

使用真实 LLM 体验：
  # 使用智谱AI + ReAct 模式
  export LLM_PROVIDER=zhipu
  export LLM_API_KEY=your-api-key
  export LLM_MODEL=glm-4
  export REASONING_TYPE=react
  python demo/02_loop_with_tools.py
""")


def demo_complex_scenario():
    """更复杂的场景：旅行规划"""
    print("\n" + "=" * 60)
    print("扩展案例：智能旅行规划")
    print("=" * 60)

    tool_registry = MockToolRegistry()

    loop = create_agent_loop(
        tool_registry=tool_registry,
        max_steps=12
    )

    user_input = """
我想从北京出发去上海旅游，请帮我：
1. 查询北京和上海今天的天气，判断是否适合出行
2. 如果适合，查询从北京到上海的航班
3. 帮我计算100美元能换多少人民币（用于预算）
"""

    print(f"用户输入: {user_input.strip()}")
    print()

    result = loop.run(user_input)

    print("-" * 60)
    print("执行结果:")
    print("-" * 60)
    print(result.trace())

    print("\n工具调用统计:")
    print(f"  总步数: {len(result.steps)}")
    print(f"  LLM调用: {result.total_llm_calls}")
    print(f"  工具调用: {result.total_tool_calls}")


if __name__ == "__main__":
    demo_loop_with_tools()
    # demo_complex_scenario()  # 可选：运行更复杂的场景