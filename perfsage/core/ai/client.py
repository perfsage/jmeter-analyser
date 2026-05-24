"""Unified AI client that dispatches to the configured LLM provider."""

from typing import Protocol


class LLMProvider(Protocol):
    """Common interface that every provider adapter must implement."""

    async def complete(self, prompt: str, *, max_tokens: int = 2048) -> str:
        """Send a prompt and return the model's text response."""
        ...


async def analyse_with_ai(metrics_json: str, provider: LLMProvider) -> str:
    """Send metrics summary to the LLM and return a plain-text analysis."""
    raise NotImplementedError
