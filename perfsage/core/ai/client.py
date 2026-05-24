"""Abstract LLM client interface and factory."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
    ) -> str:
        """Send a chat completion request. Return the text response."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return e.g. 'openai', 'anthropic', 'gemini'."""
        ...


def get_client(provider: str, api_key: str) -> LLMClient:
    """Factory: return the right LLMClient for the given provider string."""
    match provider.lower():
        case "openai":
            from perfsage.core.ai.providers.openai_provider import OpenAIClient

            return OpenAIClient(api_key)
        case "anthropic":
            from perfsage.core.ai.providers.anthropic_provider import AnthropicClient

            return AnthropicClient(api_key)
        case "gemini":
            from perfsage.core.ai.providers.gemini_provider import GeminiClient

            return GeminiClient(api_key)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider!r}")
