"""Anthropic Claude LLM provider."""

import asyncio

import anthropic

from perfsage.core.ai.client import LLMClient


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> str:
        response = await asyncio.wait_for(
            self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=timeout_seconds,
        )
        block = response.content[0]
        return block.text if hasattr(block, "text") else ""

    def provider_name(self) -> str:
        return "anthropic"
