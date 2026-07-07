from typing import Callable, Dict, Any, Optional, List, Tuple
import inspect


class ToolMetadata:
    def __init__(self, name: str, description: str, parameters: Dict[str, Dict[str, Any]], return_type: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.return_type = return_type


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tuple[Callable, ToolMetadata]] = {}

    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        if parameters is None:
            parameters = self._infer_parameters(func)

        return_type = self._infer_return_type(func)

        metadata = ToolMetadata(
            name=name,
            description=description,
            parameters=parameters,
            return_type=return_type
        )

        self._tools[name] = (func, metadata)

    def unregister_tool(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get_tool(self, name: str) -> Optional[Tuple[Callable, ToolMetadata]]:
        return self._tools.get(name)

    def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        tool_info = self._tools.get(name)
        return tool_info[1] if tool_info else None

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> Dict[str, ToolMetadata]:
        return {name: metadata for name, (_, metadata) in self._tools.items()}

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def _infer_parameters(self, func: Callable) -> Dict[str, Dict[str, Any]]:
        parameters = {}
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            param_info = {
                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "str",
                "required": param.default == inspect.Parameter.empty,
                "default": param.default if param.default != inspect.Parameter.empty else None,
                "description": ""
            }
            parameters[param_name] = param_info
        return parameters

    def _infer_return_type(self, func: Callable) -> str:
        sig = inspect.signature(func)
        return str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else "Any"


tool_registry = ToolRegistry()