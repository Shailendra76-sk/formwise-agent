import pytest
from fastapi import HTTPException

from app.auth import issue_dev_token, require_user_id
from app.config import settings


def test_legacy_header_works_only_in_non_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "allow_legacy_user_header", True)
    assert require_user_id(None, "user-1") == "user-1"


def test_production_rejects_legacy_header(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allow_legacy_user_header", True)
    with pytest.raises(HTTPException) as exc:
        require_user_id(None, "user-1")
    assert exc.value.status_code == 401


def test_jwt_auth_uses_subject(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    token = issue_dev_token("user-42", 60)
    assert require_user_id(f"Bearer {token}", None) == "user-42"


def test_production_security_rejects_default_secret(monkeypatch):
    from app.security import validate_production_security
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret", "change-me-in-production")
    monkeypatch.setattr(settings, "allow_legacy_user_header", False)
    with pytest.raises(RuntimeError):
        validate_production_security()
