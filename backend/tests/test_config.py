from tests.conftest import make_settings


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://kognisync.web.app")
    assert make_settings().cors_origins == [
        "http://localhost:5173",
        "https://kognisync.web.app",
    ]


def test_empty_secrets_are_treated_as_unset(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "  ")
    settings = make_settings()
    assert settings.gemini_api_key is None
    assert settings.database_url is None


def test_secrets_are_masked_in_repr(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "abc123")
    settings = make_settings()
    assert "abc123" not in repr(settings)
    assert settings.gemini_api_key.get_secret_value() == "abc123"


def test_production_requires_trippass_signing_key():
    import pytest

    from app.core.container import build_container

    with pytest.raises(RuntimeError, match="TRIPPASS_SIGNING_KEY"):
        build_container(make_settings(app_env="production"))
    build_container(make_settings(app_env="production", trippass_signing_key="k" * 32))
