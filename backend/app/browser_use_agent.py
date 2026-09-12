from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

from app.operational_policy import classify_page_text


class BrowserUseUnavailable(RuntimeError):
    pass


class BrowserUseSafetyError(RuntimeError):
    pass


def _validate_allowed_url(allowed_url: str) -> str:
    parsed = urlparse(allowed_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserUseSafetyError("approved URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise BrowserUseSafetyError("approved URL cannot contain embedded credentials")
    return allowed_url.strip()


async def run_browser_use_task(task: str, *, allowed_url: str | None = None, mode: str = "inspect") -> dict[str, Any]:
    """Run Browser Use as a semantic observer behind Formwise safety controls.

    Browser Use is intentionally restricted to semantic inspection. Formwise's
    deterministic Playwright executor remains responsible for field mutation,
    uploads, approvals, and final submission.
    """
    if not task or len(task) > 4000:
        raise ValueError("task must be non-empty and <= 4000 characters")
    if mode != "inspect":
        raise BrowserUseSafetyError("only semantic inspection mode is enabled")
    if not allowed_url:
        raise ValueError("allowed_url is required for Browser Use tasks")
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
    if not decision.allowed:
        return {
            "status": "paused",
            "reason": decision.reason.value if decision.reason else None,
            "message": decision.message,
            "result": result,
        }
    return {"status": "completed", "mode": "inspect", "result": result, "model": model}


def run_browser_use_task_sync(task: str, *, allowed_url: str | None = None, mode: str = "inspect") -> dict[str, Any]:
    return asyncio.run(run_browser_use_task(task, allowed_url=allowed_url, mode=mode))
