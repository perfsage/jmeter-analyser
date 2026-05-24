"""Google Gemini provider adapter for PerfSage AI client."""


class GeminiProvider:
    """LLMProvider adapter backed by the Google Generative AI API."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        """Send a prompt via Gemini and return the model's text response."""
        raise NotImplementedError
