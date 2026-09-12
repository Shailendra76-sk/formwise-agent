from __future__ import annotations

import asyncio
import os
from typing import Any


class BrowserUseUnavailable(RuntimeError):
    pass


async def run_browser_use_task(task: str, *, allowed_url: str | None = None) -> dict[str, Any]:
    """Run Browser Use behind Formwise safety boundaries.

    This adapter deliberately does not expose unrestricted submission, CAPTCHA
    solving, payment, OTP, or legal-declaration automation. The existing
    Formwise orchestrator remains the authority for approvals and submission.
    """
    if not task or len(task) > 4000:
        raise ValueError("task must be non-empty and <= 4000 characters")

    try:
        from browser_use import Agent, ChatOpenAI
    except ImportError as exc:  # pragma: no cover - exercised when optional install is absent
        raise BrowserUseUnavailable("browser-use is not installed") from exc

    # Browser Use is intentionally opt-in. Existing deterministic Playwright
    # execution remains the default until an operator enables this adapter.
    if os.getenv("FORMWISE_BROWSER_USE_ENABLED", "false").lower() != "true":
        raise BrowserUseUnavailable("Browser Use adapter is disabled")

    if not allowed_url:
        raise ValueError("allowed_url is required for Browser Use tasks")

    llm = ChatOpenAI(model=os.getenv("FORMWISE_BROWSER_USE_MODEL", "gpt-5.6-luna"))
    constrained_task = (
        f"Operate only on this approved URL: {allowed_url}. "
        "Do not bypass CAPTCHA or anti-bot controls. Do not enter OTPs, payment details, "
        "legal declarations, or perform final submission. Stop and report when any of "
        "those actions is required.\n\nTask:\n" + task
    )
    agent = Agent(task=constrained_task, llm=llm)
    history = await agent.run()
    return {"status": "completed", "result": history.final_result()}


def run_browser_use_task_sync(task: str, *, allowed_url: str | None = None) -> dict[str, Any]:
    return asyncio.run(run_browser_use_task(task, allowed_url=allowed_url))
