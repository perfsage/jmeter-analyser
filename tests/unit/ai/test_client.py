"""Unit tests for LLM client factory."""

from unittest.mock import patch

import pytest

from perfsage.core.ai.client import get_client


def test_get_client_openai() -> None:
    with patch("perfsage.core.ai.providers.openai_provider.AsyncOpenAI"):
        client = get_client("openai", "fake-key")
        assert client.provider_name() == "openai"


def test_get_client_anthropic() -> None:
    with patch("perfsage.core.ai.providers.anthropic_provider.anthropic.AsyncAnthropic"):
        client = get_client("anthropic", "fake-key")
        assert client.provider_name() == "anthropic"


def test_get_client_gemini() -> None:
    with patch("perfsage.core.ai.providers.gemini_provider.genai.Client"):
        client = get_client("gemini", "fake-key")
        assert client.provider_name() == "gemini"


def test_get_client_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_client("unknown", "key")


def test_get_client_case_insensitive() -> None:
    with patch("perfsage.core.ai.providers.openai_provider.AsyncOpenAI"):
        client = get_client("OpenAI", "fake-key")
        assert client.provider_name() == "openai"
