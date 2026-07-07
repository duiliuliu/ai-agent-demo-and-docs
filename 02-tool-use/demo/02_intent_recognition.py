from sys import path
path.append('/workspace/02-tool-use')

from skill import intent_recognizer
import json


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
    print("Demo 2 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()