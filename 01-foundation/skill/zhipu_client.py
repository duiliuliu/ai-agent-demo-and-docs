from .base_llm_client import BaseLLMClient, LLMResponse, StreamChunk
from .config_manager import LLMConfig
import openai
import time
from typing import Iterator


class ZhipuClient(BaseLLMClient):
    """
    智谱 AI API 客户端实现。
    智谱 API 兼容 OpenAI 协议，使用 base_url 指向智谱的 API 地址。
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        start_time = time.time()
        
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            latency_ms=latency_ms,
            model=model,
        )

    def stream(self, prompt: str, **kwargs) -> Iterator[StreamChunk]:
        model = kwargs.get("model", self.config.model)
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        stream = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            is_last = chunk.choices[0].finish_reason is not None
            yield StreamChunk(content=content, is_last=is_last)

    def get_supported_models(self) -> list[str]:
        return ["glm-4", "glm-4-flash", "glm-3-turbo"]
