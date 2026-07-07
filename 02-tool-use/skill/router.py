from typing import Dict, Any, Optional, List, Tuple
from .skill_manager import skill_manager
from .prompt_manager import prompt_manager
from .tool_registry import tool_registry
from .intent_recognizer import IntentAnalysis


class RouteSelection:
    def __init__(self, skill_name: str = "", prompt_name: str = "", tool_names: List[str] = None, confidence: float = 0.0):
        self.skill_name = skill_name
        self.prompt_name = prompt_name
        self.tool_names = tool_names or []
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "prompt_name": self.prompt_name,
            "tool_names": self.tool_names,
            "confidence": self.confidence
        }


class Router:
    def __init__(self):
        self._intent_routes: Dict[str, Tuple[str, str, List[str]]] = {}

    def register_route(
        self,
        intent: str,
        skill_name: str = "",
        prompt_name: str = "",
        tool_names: List[str] = None
    ) -> None:
        self._intent_routes[intent] = (skill_name, prompt_name, tool_names or [])

    def unregister_route(self, intent: str) -> bool:
        if intent in self._intent_routes:
            del self._intent_routes[intent]
            return True
        return False

    def get_route(self, intent: str) -> Optional[RouteSelection]:
        if intent in self._intent_routes:
            skill_name, prompt_name, tool_names = self._intent_routes[intent]
            return RouteSelection(
                skill_name=skill_name,
                prompt_name=prompt_name,
                tool_names=tool_names,
                confidence=1.0
            )
        return None

    def route(self, intent_analysis: IntentAnalysis) -> RouteSelection:
        primary_intent = intent_analysis.get_primary_intent()

        if primary_intent in self._intent_routes:
            skill_name, prompt_name, tool_names = self._intent_routes[primary_intent]
            return RouteSelection(
                skill_name=skill_name,
                prompt_name=prompt_name,
                tool_names=tool_names,
                confidence=intent_analysis.confidence.get("overall", 0.0)
            )

        matching_skills = skill_manager.get_skills_by_intent(primary_intent)
        if matching_skills:
            skill_name = matching_skills[0]
            skill_metadata = skill_manager.get_skill_metadata(skill_name)
            tool_names = skill_metadata.required_tools + skill_metadata.optional_tools if skill_metadata else []
            return RouteSelection(
                skill_name=skill_name,
                prompt_name="",
                tool_names=tool_names,
                confidence=intent_analysis.confidence.get("overall", 0.0)
            )

        return RouteSelection(
            skill_name="",
            prompt_name="",
            tool_names=[],
            confidence=intent_analysis.confidence.get("overall", 0.0)
        )

    def get_routes(self) -> Dict[str, Tuple[str, str, List[str]]]:
        return self._intent_routes.copy()

    def validate_route(self, route: RouteSelection) -> Dict[str, Any]:
        errors = []
        warnings = []

        if route.skill_name and not skill_manager.has_skill(route.skill_name):
            errors.append(f"Skill '{route.skill_name}' not registered")

        if route.prompt_name and not prompt_manager.has_prompt(route.prompt_name):
            errors.append(f"Prompt '{route.prompt_name}' not registered")

        for tool_name in route.tool_names:
            if not tool_registry.has_tool(tool_name):
                warnings.append(f"Tool '{tool_name}' not registered")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


router = Router()