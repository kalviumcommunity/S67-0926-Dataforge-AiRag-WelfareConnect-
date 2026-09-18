"""
Unit tests for configuration and environment settings loading.
"""

from backend.app.config import Settings


def test_settings_default_values():
    settings = Settings()
    assert settings.PROJECT_NAME == "WelfareConnect Government Scheme Assistant"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.VERSION == "1.0.0"
    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0


def test_cors_origins_parsing():
    settings = Settings(CORS_ORIGINS="http://localhost:3000,http://example.com")
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "http://example.com" in settings.CORS_ORIGINS
