import os
from sys import path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import intent_recognizer, IntentRecognizer
import json

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "base_llm_client",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '01-foundation', 'skill', 'base_llm_client.py')
    )
    if spec and spec.loader:
        base_llm_client_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(base_llm_client_module)
        BaseLLMClient = base_llm_client_module.BaseLLMClient
        LLMResponse = base_llm_client_module.LLMResponse
        HAS_FOUNDATION = True
    else:
        HAS_FOUNDATION = False
except (ImportError, FileNotFoundError):
    HAS_FOUNDATION = False


class MockLLMClient:
    def complete(self, prompt: str, **kwargs):
        print(f"[LLM调用] MockLLMClient.complete()")
        mock_result = {
            "intent": {
                "primary": "weather",
                "secondary": None,
                "is_new_topic": True,
                "description": "用户想查询天气"
            },
            "provided_info": {
                "slots": {"city": "北京"},
                "raw_mentions": ["天气", "北京"]
            },
            "missing_info": {
                "required": [],
                "optional": [],
                "ambiguous": []
            },
            "confidence": {
                "overall": 0.92,
                "intent_confidence": 0.95,
                "slot_confidence": 0.90,
                "level": "high",
                "reasoning": "意图明确，信息完整"
            },
            "execution": {
                "can_proceed": True,
                "next_action": "execute",
                "blocking_reason": "",
                "suggested_response": ""
            }
        }
        class MockResponse:
            def __init__(self, content):
                self.content = content
                self.prompt_tokens = 100
                self.completion_tokens = 200
                self.total_tokens = 300
        return MockResponse(json.dumps(mock_result, ensure_ascii=False))

    def stream(self, prompt: str, **kwargs):
        pass

    def get_supported_models(self):
        return ["mock-model"]


def print_intent_analysis(analysis):
    print(f"\n意图分析结果:")
    print(f"  主意图: {analysis.intent.get('primary')}")
    print(f"  描述: {analysis.intent.get('description')}")
    print(f"  已提供槽位: {json.dumps(analysis.provided_info.get('slots', {}), ensure_ascii=False)}")
    print(f"  原始提及: {analysis.provided_info.get('raw_mentions')}")
    print(f"  缺失必需参数: {analysis.missing_info.get('required')}")
    print(f"  置信度: {analysis.confidence.get('overall')} ({analysis.confidence.get('level')})")
    print(f"  可执行: {analysis.execution.get('can_proceed')}")
    print(f"  下一步动作: {analysis.execution.get('next_action')}")
    print(f"  建议回复: {analysis.execution.get('suggested_response')}")


def main():
    print("=" * 60)
    print("Demo 2: 意图识别")
    print("=" * 60)

    available_skills = ["weather", "book_flight", "search", "settings", "help", "general_chat"]
    print(f"可用技能列表: {available_skills}")

    print(f"\n是否加载01-foundation基础模块: {HAS_FOUNDATION}")

    print("\n" + "=" * 60)
    print("方式一: 使用内置Mock（无需LLM）")
    print("=" * 60)

    test_cases = [
        "查一下北京的天气",
        "帮我订一张下周五去杭州的机票",
        "我要从上海飞广州",
        "搜索一下人工智能最新资讯",
        "帮我设置提醒",
        "你好，今天心情怎么样",
        "这个产品怎么用",
        "明天北京到上海的航班",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"测试用例 {i}: {user_input}")
        print(f"{'='*50}")

        analysis = intent_recognizer.recognize(
            user_message=user_input,
            conversation_history=[],
            available_skills=available_skills
        )

        print_intent_analysis(analysis)

    print("\n" + "=" * 60)
    print("方式二: 接入自定义LLM客户端")
    print("=" * 60)

    mock_llm = MockLLMClient()
    custom_recognizer = IntentRecognizer(llm_client=mock_llm)

    print("\n使用MockLLMClient测试:")
    analysis = custom_recognizer.recognize(
        user_message="查北京天气",
        conversation_history=[],
        available_skills=available_skills
    )
    print_intent_analysis(analysis)

    if HAS_FOUNDATION:
        print("\n" + "=" * 60)
        print("方式三: 使用01-foundation的BaseLLMClient接口")
        print("=" * 60)
        print("提示: 可通过继承 BaseLLMClient 接入真实LLM")
        print("例如:")
        print("  from skill.base_llm_client import BaseLLMClient")
        print("  class MyLLMClient(BaseLLMClient):")
        print("      def complete(self, prompt, **kwargs):")
        print("          # 调用真实LLM API")
        print("          return LLMResponse(content='...')")
        print("  recognizer = IntentRecognizer(llm_client=MyLLMClient())")

    print("\n" + "=" * 60)
    print("Demo 2 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()