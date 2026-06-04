"""
Model factory — returns a LangChain BaseChatModel for the configured provider.

Supported providers (set LLM_PROVIDER in .env):
  openai          — OpenAI API (default)
  openai-compat   — Any OpenAI-compatible endpoint (Ollama, Groq, LM Studio, Together, etc.)
  anthropic       — Anthropic Claude API  (requires: pip install langchain-anthropic)
  google          — Google Gemini API     (requires: pip install langchain-google-genai)

For openai / openai-compat, set LLM_BASE_URL to point at a non-OpenAI host.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def get_llm(*, temperature: float = 0, streaming: bool = False) -> BaseChatModel:
    """Return a configured chat model for the active provider."""
    provider = (settings.llm_provider or "openai").lower().strip()

    if provider in ("openai", "openai-compat"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            temperature=temperature,
            streaming=streaming,
            api_key=settings.llm_api_key or settings.openai_api_key or "none",
            base_url=settings.llm_base_url or None,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is required for provider='anthropic'. "
                "Run: pip install langchain-anthropic"
            ) from exc

        return ChatAnthropic(
            model=settings.llm_model,
            temperature=temperature,
            streaming=streaming,
            api_key=settings.llm_api_key or settings.openai_api_key or "none",
        )

    if provider in ("google", "gemini"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "langchain-google-genai is required for provider='google'. "
                "Run: pip install langchain-google-genai"
            ) from exc

        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            temperature=temperature,
            streaming=streaming,
            google_api_key=settings.llm_api_key or settings.openai_api_key or "none",
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. "
        "Choose one of: openai, openai-compat, anthropic, google"
    )


def get_vision_llm() -> BaseChatModel:
    """Return a vision-capable chat model using the configured vision_model.

    Raises:
        ValueError: If vision_model is not configured (empty string).
    """
    if not settings.vision_model:
        raise ValueError(
            "vision_model is not configured. "
            "Set VISION_MODEL in .env to enable vision extraction."
        )

    provider = (settings.llm_provider or "openai").lower().strip()

    if provider in ("openai", "openai-compat"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.vision_model,
            temperature=0,
            api_key=settings.llm_api_key or settings.openai_api_key or "none",
            base_url=settings.llm_base_url or None,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is required for provider='anthropic'. "
                "Run: pip install langchain-anthropic"
            ) from exc

        return ChatAnthropic(
            model=settings.vision_model,
            temperature=0,
            api_key=settings.llm_api_key or settings.openai_api_key or "none",
        )

    if provider in ("google", "gemini"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "langchain-google-genai is required for provider='google'. "
                "Run: pip install langchain-google-genai"
            ) from exc

        return ChatGoogleGenerativeAI(
            model=settings.vision_model,
            temperature=0,
            google_api_key=settings.llm_api_key or settings.openai_api_key or "none",
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. "
        "Choose one of: openai, openai-compat, anthropic, google"
    )
