from typing import Dict, Any, Optional, Tuple, List
from .tool_registry import tool_registry, ToolMetadata


class ToolExecutionResult:
    def __init__(self, success: bool, result: Any = None, error: str = "", tool_name: str = ""):
        self.success = success
        self.result = result
        self.error = error
        self.tool_name = tool_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "tool_name": self.tool_name
        }


class ToolExecutor:
    def __init__(self):
        pass

    def execute(
        self,
        tool_name: str,
        **kwargs: Any
    ) -> ToolExecutionResult:
        tool_info = tool_registry.get_tool(tool_name)
        if not tool_info:
            return ToolExecutionResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                tool_name=tool_name
            )

        func, metadata = tool_info

        missing_params = []
        for param_name, param_info in metadata.parameters.items():
            if param_info["required"] and param_name not in kwargs:
                missing_params.append(param_name)

        if missing_params:
            return ToolExecutionResult(
                success=False,
                error=f"Missing required parameters: {', '.join(missing_params)}",
                tool_name=tool_name
            )

        try:
            result = func(**kwargs)
            return ToolExecutionResult(
                success=True,
                result=result,
                tool_name=tool_name
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_name=tool_name
            )

    def batch_execute(
        self,
        tasks: List[Tuple[str, Dict[str, Any]]]
    ) -> List[ToolExecutionResult]:
        results = []
        for tool_name, kwargs in tasks:
            result = self.execute(tool_name, **kwargs)
            results.append(result)
        return results


tool_executor = ToolExecutor()