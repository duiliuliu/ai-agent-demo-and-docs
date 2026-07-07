from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""


@dataclass
class StreamChunk:
    content: str
    is_last: bool = False


class BaseLLMClient(ABC):
    """
    LLM 调用抽象基类，定义统一接口。
    所有具体 LLM 实现（OpenAI、智普、DeepSeek 等）都必须实现这些方法。
    """

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        同步调用 LLM，返回完整响应。

        Args:
            prompt: 用户输入的提示词
            **kwargs: 可选参数，如 temperature, max_tokens, model 等

        Returns:
            LLMResponse: 包含响应内容、token 消耗、延迟等信息
        """
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[StreamChunk]:
        """
        流式调用 LLM，逐 token 返回。

        Args:
            prompt: 用户输入的提示词
            **kwargs: 可选参数，如 temperature, max_tokens, model 等

        Yields:
            StreamChunk: 流式返回的内容片段
        """
        pass

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """
        返回当前客户端支持的模型列表

        Returns:
            list[str]: 模型名称列表
        """
        pass
