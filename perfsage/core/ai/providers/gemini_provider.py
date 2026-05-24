"""Google Gemini LLM provider."""

import asyncio

import google.genai as genai

from perfsage.core.ai.client import LLMClient


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> str:
        from google.genai import types as gtypes

        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self._model,
                    contents=f"{system_prompt}\n\n{user_prompt}",
                    config=gtypes.GenerateContentConfig(max_output_tokens=max_tokens),
                ),
            ),
            timeout=timeout_seconds,
        )
        return response.text or ""

    def provider_name(self) -> str:
        return "gemini"
