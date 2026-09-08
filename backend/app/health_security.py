from app.config import settings


def security_status() -> dict[str, object]:
    production = settings.environment == "production"
    return {
        "environment": settings.environment,
        "jwt_configured": settings.jwt_secret != "change-me-in-production" and len(settings.jwt_secret) >= 32,
        "legacy_user_header_allowed": bool(settings.allow_legacy_user_header and not production),
        "private_network_blocking": settings.browser_block_private_networks,
        "final_submission_automation": False,
        "captcha_bypass": False,
        "otp_automation": False,
        "payment_automation": False,
    }
