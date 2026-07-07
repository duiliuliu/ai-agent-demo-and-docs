from typing import Dict, Any, Optional, List, Tuple
from .tool_registry import ToolMetadata


class SkillMetadata:
    def __init__(
        self,
        name: str,
        description: str,
        required_tools: List[str],
        optional_tools: List[str],
        supported_intents: List[str],
        config_schema: Dict[str, Any] = None
    ):
        self.name = name
        self.description = description
        self.required_tools = required_tools
        self.optional_tools = optional_tools
        self.supported_intents = supported_intents
        self.config_schema = config_schema or {}


class SkillManager:
    def __init__(self):
        self._skills: Dict[str, Tuple[Any, SkillMetadata]] = {}

    def register_skill(
        self,
        name: str,
        skill_instance: Any,
        description: str = "",
        required_tools: List[str] = None,
        optional_tools: List[str] = None,
        supported_intents: List[str] = None,
        config_schema: Dict[str, Any] = None
    ) -> None:
        if required_tools is None:
            required_tools = []
        if optional_tools is None:
            optional_tools = []
        if supported_intents is None:
            supported_intents = []

        metadata = SkillMetadata(
            name=name,
            description=description,
            required_tools=required_tools,
            optional_tools=optional_tools,
            supported_intents=supported_intents,
            config_schema=config_schema
        )

        self._skills[name] = (skill_instance, metadata)

    def unregister_skill(self, name: str) -> bool:
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get_skill(self, name: str) -> Optional[Tuple[Any, SkillMetadata]]:
        return self._skills.get(name)

    def get_skill_metadata(self, name: str) -> Optional[SkillMetadata]:
        skill_info = self._skills.get(name)
        return skill_info[1] if skill_info else None

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def get_all_skills(self) -> Dict[str, SkillMetadata]:
        return {name: metadata for name, (_, metadata) in self._skills.items()}

    def has_skill(self, name: str) -> bool:
        return name in self._skills

    def get_skills_by_intent(self, intent: str) -> List[str]:
        matching_skills = []
        for name, (_, metadata) in self._skills.items():
            if intent in metadata.supported_intents:
                matching_skills.append(name)
        return matching_skills

    def get_skills_by_tool(self, tool_name: str) -> List[str]:
        matching_skills = []
        for name, (_, metadata) in self._skills.items():
            if tool_name in metadata.required_tools or tool_name in metadata.optional_tools:
                matching_skills.append(name)
        return matching_skills


skill_manager = SkillManager()