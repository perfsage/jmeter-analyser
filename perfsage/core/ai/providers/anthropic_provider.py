"""Anthropic provider adapter for PerfSage AI client."""


class AnthropicProvider:
    """LLMProvider adapter backed by the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str = "claude-opus-4-5") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        """Send a prompt via Anthropic and return the assistant's text response."""
        raise NotImplementedError
