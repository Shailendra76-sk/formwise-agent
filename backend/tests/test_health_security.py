from app.config import settings
from app.health_security import security_status


def test_security_status_never_allows_submission_automation():
    status = security_status()
    assert status["final_submission_automation"] is False
    assert status["captcha_bypass"] is False
    assert status["otp_automation"] is False
    assert status["payment_automation"] is False


def test_security_status_reports_private_network_blocking(monkeypatch):
    monkeypatch.setattr(settings, "browser_block_private_networks", True)
    assert security_status()["private_network_blocking"] is True
