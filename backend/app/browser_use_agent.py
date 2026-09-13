from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

from app.operational_policy import classify_page_text
from app.verified_data_service import VerifiedDataResult, VerifiedDataService
from app.database import SessionLocal


class BrowserUseUnavailable(RuntimeError):
    pass


class BrowserUseSafetyError(RuntimeError):
    pass


async def request_verified_field(
    user_id: str,
    field_key: str,
    *,
    session_id: str | None = None,
) -> VerifiedDataResult:
    """Read exactly one allow-listed field from the verified DB gateway.

    A non-VERIFIED result fails closed and, for a live session, asks the live
    browser manager to unlock human control. Values are never sent to the
    browser frontend by this helper.
    """
    db = SessionLocal()
    try:
        result = VerifiedDataService(db).get_field(user_id, field_key)
    finally:
        db.close()

    if not result.usable and session_id:
        from app.live_browser import live_manager

        await live_manager.require_human_for_verified_data(session_id, field_key, result)
    return result


def _validate_allowed_url(allowed_url: str) -> str:
    parsed = urlparse(allowed_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserUseSafetyError("approved URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise BrowserUseSafetyError("approved URL cannot contain embedded credentials")
    return allowed_url.strip()


async def run_browser_use_task(
    task: str,
    *,
    allowed_url: str | None = None,
    mode: str = "inspect",
    user_id: str | None = None,
    session_id: str | None = None,
    requested_field: str | None = None,
) -> dict[str, Any]:
    """Run Browser Use as a semantic observer behind Formwise safety controls.

    When requested_field is present, the adapter obtains only that single
    approved value through VerifiedDataService before the browser inspection.
    Browser Use remains inspection-only; deterministic Formwise execution owns
    field mutation, uploads, approvals, and final submission.
    """
    if not task or len(task) > 4000:
        raise ValueError("task must be non-empty and <= 4000 characters")
    if mode != "inspect":
        raise BrowserUseSafetyError("only semantic inspection mode is enabled")
    if not allowed_url:
        raise ValueError("allowed_url is required for Browser Use tasks")
    if requested_field and not user_id:
        raise ValueError("user_id is required when requested_field is supplied")

    verified_field: VerifiedDataResult | None = None
    if requested_field:
        verified_field = await request_verified_field(user_id, requested_field, session_id=session_id)
        if not verified_field.usable:
            return {
                "status": "paused",
                "reason": verified_field.status.lower(),
                "message": verified_field.message,
                "requested_field": requested_field,
            }

    safe_url = _validate_allowed_url(allowed_url)
    approved_host = urlparse(safe_url).hostname.lower()

    if os.getenv("FORMWISE_BROWSER_USE_ENABLED", "false").lower() != "true":
        raise BrowserUseUnavailable("Browser Use adapter is disabled")

    try:
        from browser_use import Agent, ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise BrowserUseUnavailable("browser-use is not installed") from exc

    model = os.getenv("FORMWISE_BROWSER_USE_MODEL", "gpt-5.6-luna")
    llm = ChatOpenAI(model=model)
    constrained_task = (
        f"Inspect only this approved website: {safe_url}. Stay on the same hostname ({approved_host}). "
        "Semantic inspection only: do NOT fill, click, upload, submit, or modify data. "
        "Do NOT solve or bypass CAPTCHA/reCAPTCHA/hCaptcha or anti-bot controls. "
        "Do NOT enter or handle OTP/verification codes. Do NOT accept legal declarations. "
        "Do NOT make payments. Do NOT click final submission or confirmation buttons. "
        "Report page title, current URL, visible form sections, field labels/names/types, "
        "required fields, verification gates, and obvious intermediate navigation steps. "
        "Stop immediately when a restricted gate appears. Do not follow advertisements "
        "or unrelated external links.\n\nTask:\n" + task
    )
    agent = Agent(task=constrained_task, llm=llm)
    history = await agent.run()
    result = history.final_result()
    decision = classify_page_text(result)
    response: dict[str, Any] = {
        "status": "paused" if not decision.allowed else "completed",
        "mode": "inspect",
        "result": result,
        "model": model,
    }
    if verified_field is not None:
        response["requested_field"] = verified_field.field_key
        response["verified_value"] = verified_field.value if verified_field.usable else None
        response["verified_source"] = verified_field.source
    if not decision.allowed:
        response["reason"] = decision.reason.value if decision.reason else None
        response["message"] = decision.message
    return response


def run_browser_use_task_sync(
    task: str,
    *,
    allowed_url: str | None = None,
    mode: str = "inspect",
    user_id: str | None = None,
    session_id: str | None = None,
    requested_field: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        run_browser_use_task(
            task,
            allowed_url=allowed_url,
            mode=mode,
            user_id=user_id,
            session_id=session_id,
            requested_field=requested_field,
        )
    )
