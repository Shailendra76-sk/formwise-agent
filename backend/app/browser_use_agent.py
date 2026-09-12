from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

from app.operational_policy import action_decision, classify_page_text


class BrowserUseUnavailable(RuntimeError):
    pass


async def run_browser_use_task(task: str, *, allowed_url: str | None = None) -> dict[str, Any]:
    """Run Browser Use only for safe, non-consequential browser work."""
    if not task or len(task) > 4000:
        raise ValueError("task must be non-empty and <= 4000 characters")
    if not allowed_url:
        raise ValueError("allowed_url is required for Browser Use tasks")
    parsed = urlparse(allowed_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("allowed_url must be an absolute HTTP(S) URL")

    task_decision = classify_page_text(task)
    if not task_decision.allowed:
        raise BrowserUseUnavailable(task_decision.message or "Browser Use task is safety-blocked")

    if os.getenv("FORMWISE_BROWSER_USE_ENABLED", "false").lower() != "true":
        raise BrowserUseUnavailable("Browser Use adapter is disabled")

    try:
        from browser_use import Agent, ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise BrowserUseUnavailable("browser-use is not installed") from exc

    model = os.getenv("FORMWISE_BROWSER_USE_MODEL", "gpt-5.6-luna")
    llm = ChatOpenAI(model=model)
    constrained_task = (
        f"Operate only on this approved URL and its same-site pages: {allowed_url}. "
        "You are a Formwise browser assistant. Inspect and fill only fields that can be "
        "filled from verified Formwise data. Never invent data. Never solve, bypass, or "
        "interact with CAPTCHA/anti-bot challenges. Never enter OTP or verification codes. "
        "Never accept legal declarations or self-attestation. Never enter payment or banking "
        "details. Never click final Submit, Confirm Application, Pay & Submit, or equivalent. "
        "You may use Next, Continue, or Save Draft when they are clearly intermediate. "
        "If any restricted step appears, stop immediately and report PAUSED with the reason. "
        "Do not follow advertisements or navigate to unrelated external sites.\n\nTask:\n" + task
    )
    agent = Agent(task=constrained_task, llm=llm)
    history = await agent.run()
    result = history.final_result()
    decision = classify_page_text(result)
    if not decision.allowed:
        return {"status": "paused", "reason": decision.reason.value if decision.reason else None, "message": decision.message, "result": result}
    # Guard the model's textual result too; a Browser Use result is never an approval to submit.
    submit_decision = action_decision("submit")
    return {"status": "completed", "result": result, "submission_allowed": submit_decision.allowed}


def run_browser_use_task_sync(task: str, *, allowed_url: str | None = None) -> dict[str, Any]:
    return asyncio.run(run_browser_use_task(task, allowed_url=allowed_url))
