"""OpenAI provider adapter for PerfSage AI client."""


class OpenAIProvider:
    """LLMProvider adapter backed by the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        """Send a prompt via OpenAI and return the assistant's text response."""
        raise NotImplementedError
