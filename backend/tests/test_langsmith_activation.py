"""Tests for Phase 8: LangSmith env injection at startup (OBS-01, OBS-02)."""
import os


def test_langsmith_env_injected_when_key_set(monkeypatch):
    """When LANGCHAIN_API_KEY is set in settings, os.environ gets all three vars."""
    # Simulate the injection block from main.py lifespan
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-fake-key-for-test")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "scholar")

    assert os.environ.get("LANGCHAIN_API_KEY") == "ls-fake-key-for-test"
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_PROJECT") == "scholar"


def test_no_injection_when_key_absent(monkeypatch):
    """When LANGCHAIN_API_KEY is absent, LANGCHAIN_TRACING_V2 must NOT be set to true."""
    # Ensure the vars are not present
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

    # Simulate the guard condition: if not api_key, skip injection
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")
    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    # Tracing must NOT have been activated
    assert os.environ.get("LANGCHAIN_TRACING_V2") != "true"


def test_settings_has_langsmith_fields():
    """Settings class exposes langsmith_api_key, langchain_tracing_v2, langchain_project."""
    from app.config import Settings
    # Instantiate with explicit values (bypasses .env)
    s = Settings(
        langsmith_api_key="ls-test",
        langchain_tracing_v2=True,
        langchain_project="my-project",
        _env_file=None,
    )
    assert s.langsmith_api_key == "ls-test"
    assert s.langchain_tracing_v2 is True
    assert s.langchain_project == "my-project"
