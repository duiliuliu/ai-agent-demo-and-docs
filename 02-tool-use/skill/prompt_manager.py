from typing import Dict, Any, Optional, List
import json


class PromptTemplate:
    def __init__(self, name: str, template: str, description: str = "", required_vars: List[str] = None):
        self.name = name
        self.template = template
        self.description = description
        self.required_vars = required_vars or []


class PromptManager:
    def __init__(self):
        self._prompts: Dict[str, PromptTemplate] = {}

    def register_prompt(
        self,
        name: str,
        template: str,
        description: str = "",
        required_vars: Optional[List[str]] = None
    ) -> None:
        prompt = PromptTemplate(
            name=name,
            template=template,
            description=description,
            required_vars=required_vars or []
        )
        self._prompts[name] = prompt

    def unregister_prompt(self, name: str) -> bool:
        if name in self._prompts:
            del self._prompts[name]
            return True
        return False

    def get_prompt(self, name: str) -> Optional[PromptTemplate]:
        return self._prompts.get(name)

    def list_prompts(self) -> List[str]:
        return list(self._prompts.keys())

    def get_all_prompts(self) -> Dict[str, PromptTemplate]:
        return self._prompts.copy()

    def has_prompt(self, name: str) -> bool:
        return name in self._prompts

    def render_prompt(self, name: str, **kwargs: Any) -> Optional[str]:
        prompt = self._prompts.get(name)
        if not prompt:
            return None

        missing_vars = [var for var in prompt.required_vars if var not in kwargs]
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")

        try:
            return prompt.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable in template: {e}")


INTENT_RECOGNITION_PROMPT = """
你是一个意图识别引擎。请根据用户的输入，完成以下结构化分析：

输入
用户消息：{user_message}
对话历史：{conversation_history}
可用业务/能力列表：{available_skills}

输出要求

请严格按以下 JSON 结构输出分析结果：

{{
  "intent": {{
    "primary": "用户当前想办的核心事项（从 available_skills 中匹配最接近的能力名称）",
    "secondary": "可能同时存在的次要意图（如有，否则为 null）",
    "is_new_topic": true,
    "description": "用一句话概括用户想做什么"
  }},
  "provided_info": {{
    "slots": {{
      "参数名1": "用户已提供的值",
      "参数名2": "用户已提供的值"
    }},
    "raw_mentions": ["用户原文中提到的关键实体/关键词"]
  }},
  "missing_info": {{
    "required": ["必须提供但尚未提供的参数列表"],
    "optional": ["可选但建议补充的参数列表"],
    "ambiguous": [
      {{
        "field": "有歧义的字段名",
        "possible_values": ["候选值1", "候选值2"],
        "reason": "为什么存在歧义"
      }}
    ]
  }},
  "confidence": {{
    "overall": 0.92,
    "intent_confidence": 0.95,
    "slot_confidence": 0.88,
    "level": "high",
    "reasoning": "置信度判断依据说明"
  }},
  "execution": {{
    "can_proceed": false,
    "next_action": "ask_user | execute | clarify | escalate",
    "blocking_reason": "如果不能执行，说明阻塞原因",
    "suggested_response": "建议对用户说的话（用于追问缺失信息或确认意图）"
  }}
}}

判断规则

意图识别（intent）
primary：从 available_skills 中匹配最贴合的能力；若无匹配，标记为 "unknown"
secondary：识别用户是否在一句话中表达了多个意图
is_new_topic：对比对话历史，判断是否为话题切换

已提供信息（provided_info）
slots：提取用户消息中所有可识别的结构化参数
raw_mentions：保留原文关键实体，不做过度推断

缺失信息（missing_info）
required：对照 primary 意图的参数 schema，列出必须但缺失的字段
optional：列出可选但有助于提升执行质量的字段
ambiguous：标记用户表述模糊、可能对应多个值的字段

置信度（confidence）
overall：综合置信度（0-1）
intent_confidence：意图判断的置信度
slot_confidence：槽位填充的置信度
level：high(≥0.85) / medium(0.6-0.85) / low(<0.6)
reasoning：给出置信度判断的理由

执行判断（execution）
can_proceed：所有 required 参数是否齐全且无歧义
next_action：
  execute：信息充分，可直接执行
  ask_user：缺少必要信息，需追问
  clarify：信息有歧义，需确认
  escalate：超出能力范围，需转人工
blocking_reason：can_proceed 为 false 时的具体原因
suggested_response：生成一句自然的追问/确认话术
"""


prompt_manager = PromptManager()
prompt_manager.register_prompt(
    name="intent_recognition",
    template=INTENT_RECOGNITION_PROMPT,
    description="意图识别Prompt模板，用于分析用户意图、提取槽位、检测缺失信息和歧义",
    required_vars=["user_message", "conversation_history", "available_skills"]
)