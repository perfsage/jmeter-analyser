"""OpenAI GPT-4 LLM provider."""

import asyncio

from openai import AsyncOpenAI

from perfsage.core.ai.client import LLMClient


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> str:
        response = await asyncio.wait_for(
            self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
            ),
            timeout=timeout_seconds,
        )
        return response.choices[0].message.content or ""

    def provider_name(self) -> str:
        return "openai"
