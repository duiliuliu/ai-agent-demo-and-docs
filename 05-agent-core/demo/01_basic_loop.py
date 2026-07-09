"""
Demo 01: 最简 Agent 核心循环

场景：展示最基本的 Observation-Thought-Action 循环
目标：让读者理解 Agent 循环的本质——观察→思考→行动→再观察

核心知识点：
  1. AgentLoop 的基本使用方式
  2. 理解 Observation、Thought、Action 三个阶段
  3. 循环的终止条件（最大步数）
  4. 如何获取循环执行的详细轨迹

支持真实 LLM：
  设置环境变量即可使用真实 LLM：
    export LLM_PROVIDER=openai
    export LLM_API_KEY=your-api-key
    export LLM_MODEL=gpt-3.5-turbo
    export REASONING_TYPE=simple

运行方式：
  python demo/01_basic_loop.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_helper import create_agent_loop, print_config_info


def demo_basic_loop():
    print_config_info()

    loop = create_agent_loop(max_steps=3)

    user_input = "帮我分析一下今天的天气情况"

    print(f"用户输入: {user_input}")
    print(f"最大步数: {loop.max_steps}")
    print()

    result = loop.run(user_input)

    print("-" * 60)
    print("执行结果:")
    print("-" * 60)
    print(result.trace())
    print()

    print("=" * 60)
    print("核心概念解析")
    print("=" * 60)
    print("""
1. Observation（观察）：Agent 感知到的外部输入
   - 用户消息、工具返回、系统事件等
   - 本示例中：用户输入 "帮我分析一下今天的天气情况"

2. Thought（思考）：Agent 对当前状态和目标的内部推理
   - 由推理引擎生成
   - 决定下一步应该做什么

3. Action（行动）：Agent 对外部环境的输出
   - 回复用户、调用工具、调用其他 Agent
   - 本示例中：根据思考内容进行响应

4. Termination（终止）：循环的退出条件
   - 任务完成、达到最大步数、用户中断、发生致命错误
   - 本示例中：达到最大步数(3)后终止

循环流程：
  Observation → Thought → Action → (观察结果) → Observation → ...
""")


if __name__ == "__main__":
    demo_basic_loop()
