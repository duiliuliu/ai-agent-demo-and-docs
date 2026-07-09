"""
Demo 03: 带记忆读写的 Agent 循环

场景：展示如何在 Agent 循环中集成记忆模块（结合上下文管理）
目标：理解记忆在多轮对话和长期交互中的作用

核心知识点：
  1. 记忆加载和存储机制
  2. 上下文与记忆的交互
  3. 短期记忆（上下文历史）和长期记忆的区别
  4. 记忆在循环中的使用流程

支持真实 LLM：
  设置环境变量即可使用真实 LLM + CoT 推理：
    export LLM_PROVIDER=openai
    export LLM_API_KEY=your-api-key
    export LLM_MODEL=gpt-3.5-turbo
    export REASONING_TYPE=cot

运行方式：
  python demo/03_loop_with_memory.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_helper import create_agent_loop, print_config_info
from skill.context_manager import EnhancedContextManager


class MockMemoryStore:
    def __init__(self):
        self._memory = {
            "user_profile": {
                "name": "张三",
                "preferences": ["喜欢晴天", "喜欢去北京旅游", "预算有限"],
                "history": ["之前查询过北京天气", "对航班价格敏感"]
            },
            "knowledge_base": {
                "北京": "中国首都，著名景点有故宫、天安门、长城",
                "上海": "中国最大城市，经济中心，外滩夜景著名",
                "广州": "南方重要城市，美食之都"
            }
        }

    def retrieve(self, query: str, limit: int = 5) -> dict:
        facts = []
        interactions = []

        if "北京" in query:
            facts.append(self._memory["knowledge_base"]["北京"])
        if "上海" in query:
            facts.append(self._memory["knowledge_base"]["上海"])
        if "广州" in query:
            facts.append(self._memory["knowledge_base"]["广州"])

        interactions = self._memory["user_profile"]["history"][:limit]

        return {"facts": facts[:limit], "interactions": interactions}

    def store(self, data: str) -> None:
        self._memory["user_profile"]["history"].append(data)
        if len(self._memory["user_profile"]["history"]) > 10:
            self._memory["user_profile"]["history"] = self._memory["user_profile"]["history"][-10:]


def demo_loop_with_memory():
    print_config_info()

    memory_store = MockMemoryStore()

    context_manager = EnhancedContextManager(
        memory_store=memory_store,
        max_history_length=5
    )

    loop = create_agent_loop(
        memory_store=memory_store,
        max_steps=4
    )

    user_input = "我想去北京旅游，帮我分析一下"

    print(f"用户输入: {user_input}")
    print()

    context_manager.initialize(user_input)
    context_manager.load_from_memory()

    print("初始上下文（含记忆）:")
    ctx = context_manager.get_context()
    print(f"  用户输入: {ctx.get('user_input')}")
    print(f"  记忆中的事实: {ctx.get('memory', {}).get('relevant_facts', [])}")
    print(f"  历史交互: {ctx.get('memory', {}).get('previous_interactions', [])}")
    print()

    result = loop.run(user_input, context=ctx)

    print("-" * 60)
    print("执行结果:")
    print("-" * 60)
    print(result.trace())
    print()

    for step in result.steps:
        context_manager.update_history({
            "step_id": step.step_id,
            "thought": step.thought,
            "action": step.action.to_dict() if step.action else None,
            "result": step.result
        })

    context_manager.save_to_memory()

    print("最终上下文摘要:")
    try:
        summary = context_manager.get_context_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"  (获取摘要时出现问题: {e})")
    print()

    print("=" * 60)
    print("记忆机制解析")
    print("=" * 60)
    print("""
1. 记忆类型：
   - 短期记忆（上下文历史）：本次对话的步骤记录
   - 长期记忆（Memory Store）：跨对话的持久化信息

2. 记忆加载流程：
   - 在循环开始前，从记忆存储中检索相关信息
   - 信息被加载到上下文中，供推理引擎使用
   - 本示例中：加载了用户偏好和知识库信息

3. 记忆存储流程：
   - 在循环结束后，提取关键信息
   - 将新信息存入记忆存储
   - 支持后续对话使用

4. 上下文压缩：
   - 当历史记录超过最大长度时，自动压缩旧记录
   - 保留最近的详细记录，旧记录摘要化
   - 防止上下文无限增长

5. 实际应用场景：
   - 用户画像：记住用户偏好和习惯
   - 知识积累：积累领域知识
   - 会话连续性：跨会话保持上下文
   - 个性化服务：根据用户历史提供定制化建议

使用真实 LLM 体验：
  # 使用智谱AI + CoT 模式
  export LLM_PROVIDER=zhipu
  export LLM_API_KEY=your-api-key
  export REASONING_TYPE=cot
  python demo/03_loop_with_memory.py
""")


if __name__ == "__main__":
    demo_loop_with_memory()
