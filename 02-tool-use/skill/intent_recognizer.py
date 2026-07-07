from typing import Dict, Any, Optional, List
import json
import re
from .prompt_manager import prompt_manager


class IntentAnalysis:
    def __init__(self, data: Dict[str, Any]):
        self.intent = data.get("intent", {})
        self.provided_info = data.get("provided_info", {})
        self.missing_info = data.get("missing_info", {})
        self.confidence = data.get("confidence", {})
        self.execution = data.get("execution", {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "provided_info": self.provided_info,
            "missing_info": self.missing_info,
            "confidence": self.confidence,
            "execution": self.execution
        }

    def can_proceed(self) -> bool:
        return self.execution.get("can_proceed", False)

    def get_next_action(self) -> str:
        return self.execution.get("next_action", "ask_user")

    def get_suggested_response(self) -> str:
        return self.execution.get("suggested_response", "")

    def get_primary_intent(self) -> str:
        return self.intent.get("primary", "unknown")


class IntentRecognizer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def recognize(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        available_skills: List[str] = None
    ) -> IntentAnalysis:
        if conversation_history is None:
            conversation_history = []
        if available_skills is None:
            available_skills = []

        history_str = json.dumps(conversation_history, ensure_ascii=False)
        skills_str = json.dumps(available_skills, ensure_ascii=False)

        prompt = prompt_manager.render_prompt(
            "intent_recognition",
            user_message=user_message,
            conversation_history=history_str,
            available_skills=skills_str
        )

        if self.llm_client:
            llm_response = self.llm_client.complete(prompt)
            if hasattr(llm_response, 'content'):
                response = llm_response.content
            else:
                response = str(llm_response)
        else:
            response = self._mock_intent_recognition(user_message, available_skills)

        return self._parse_response(response)

    def _parse_response(self, response: str) -> IntentAnalysis:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                return IntentAnalysis(data)
            else:
                return IntentAnalysis({
                    "intent": {
                        "primary": "unknown",
                        "secondary": None,
                        "is_new_topic": True,
                        "description": "无法解析意图"
                    },
                    "provided_info": {
                        "slots": {},
                        "raw_mentions": []
                    },
                    "missing_info": {
                        "required": [],
                        "optional": [],
                        "ambiguous": []
                    },
                    "confidence": {
                        "overall": 0.0,
                        "intent_confidence": 0.0,
                        "slot_confidence": 0.0,
                        "level": "low",
                        "reasoning": "无法解析JSON响应"
                    },
                    "execution": {
                        "can_proceed": False,
                        "next_action": "escalate",
                        "blocking_reason": "意图识别失败",
                        "suggested_response": "抱歉，我无法理解您的请求，请您换一种方式表达。"
                    }
                })
        except json.JSONDecodeError:
            return IntentAnalysis({
                "intent": {
                    "primary": "unknown",
                    "secondary": None,
                    "is_new_topic": True,
                    "description": "无法解析意图"
                },
                "provided_info": {
                    "slots": {},
                    "raw_mentions": []
                },
                "missing_info": {
                    "required": [],
                    "optional": [],
                    "ambiguous": []
                },
                "confidence": {
                    "overall": 0.0,
                    "intent_confidence": 0.0,
                    "slot_confidence": 0.0,
                    "level": "low",
                    "reasoning": "JSON解析失败"
                },
                "execution": {
                    "can_proceed": False,
                    "next_action": "escalate",
                    "blocking_reason": "意图识别失败",
                    "suggested_response": "抱歉，我无法理解您的请求，请您换一种方式表达。"
                }
            })

    def _mock_intent_recognition(self, user_message: str, available_skills: List[str]) -> str:
        intent_map = {
            "天气": "weather",
            "航班": "book_flight",
            "机票": "book_flight",
            "预订": "book_flight",
            "查询": "search",
            "搜索": "search",
            "设置": "settings",
            "帮助": "help",
            "聊天": "general_chat",
            "对话": "general_chat"
        }

        primary_intent = "unknown"
        for keyword, intent in intent_map.items():
            if keyword in user_message:
                primary_intent = intent
                break

        provided_slots = {}
        raw_mentions = []
        missing_required = []

        if primary_intent == "weather":
            if "北京" in user_message:
                provided_slots["city"] = "北京"
            elif "上海" in user_message:
                provided_slots["city"] = "上海"
            else:
                missing_required = ["city"]
            raw_mentions = ["天气"]
            if provided_slots.get("city"):
                raw_mentions.append(provided_slots["city"])

        elif primary_intent == "book_flight":
            city_pattern = r"(北京|上海|广州|深圳|杭州|成都|重庆)"
            cities = re.findall(city_pattern, user_message)
            if len(cities) >= 2:
                provided_slots["departure_city"] = cities[0]
                provided_slots["destination"] = cities[1]
            elif len(cities) == 1:
                provided_slots["destination"] = cities[0]
                missing_required = ["departure_city"]
            else:
                missing_required = ["departure_city", "destination"]

            date_pattern = r"(今天|明天|后天|下周一|下周二|下周三|下周四|下周五|下周六|下周日|\d{4}-\d{2}-\d{2})"
            dates = re.findall(date_pattern, user_message)
            if dates:
                provided_slots["departure_date"] = dates[0]
            else:
                missing_required.append("departure_date")

            raw_mentions = ["机票", "航班"] + cities + dates

        elif primary_intent == "search":
            raw_mentions = ["搜索", "查询"]

        elif primary_intent == "settings":
            raw_mentions = ["设置"]

        elif primary_intent == "help":
            raw_mentions = ["帮助"]

        elif primary_intent == "general_chat":
            raw_mentions = ["聊天"]

        can_proceed = len(missing_required) == 0
        next_action = "execute" if can_proceed else "ask_user"

        overall_confidence = 0.85 if primary_intent != "unknown" else 0.3
        intent_confidence = 0.9 if primary_intent != "unknown" else 0.1
        slot_confidence = 0.8 if can_proceed else 0.5
        level = "high" if overall_confidence >= 0.85 else ("medium" if overall_confidence >= 0.6 else "low")

        suggested_response = ""
        if not can_proceed:
            if primary_intent == "weather":
                suggested_response = "好的，想查询天气。请问是哪个城市呢？"
            elif primary_intent == "book_flight":
                missing_str = "、".join(missing_required)
                suggested_response = f"好的，帮您预订机票。还需要补充以下信息：{missing_str}"
            else:
                suggested_response = "我需要更多信息来帮您完成请求。"

        result = {
            "intent": {
                "primary": primary_intent,
                "secondary": None,
                "is_new_topic": True,
                "description": f"用户想{user_message}"
            },
            "provided_info": {
                "slots": provided_slots,
                "raw_mentions": raw_mentions
            },
            "missing_info": {
                "required": missing_required,
                "optional": [],
                "ambiguous": []
            },
            "confidence": {
                "overall": overall_confidence,
                "intent_confidence": intent_confidence,
                "slot_confidence": slot_confidence,
                "level": level,
                "reasoning": f"意图明确为{primary_intent}" if primary_intent != "unknown" else "无法识别意图"
            },
            "execution": {
                "can_proceed": can_proceed,
                "next_action": next_action,
                "blocking_reason": f"缺少必要参数: {', '.join(missing_required)}" if missing_required else "",
                "suggested_response": suggested_response
            }
        }

        return json.dumps(result, ensure_ascii=False)


intent_recognizer = IntentRecognizer()