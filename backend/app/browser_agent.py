from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Route, Request, async_playwright

from app.config import settings


class BrowserSafetyError(ValueError):
    pass


class BrowserSessionNotFound(KeyError):
    pass


@dataclass
class BrowserSession:
    session_id: str
    user_id: str
    browser: Browser
    context: BrowserContext
    page: Page
    created_at: float
    last_used_at: float


_SESSIONS: dict[str, BrowserSession] = {}
_LOCK = asyncio.Lock()
_PLAYWRIGHT: Playwright | None = None


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def validate_navigation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserSafetyError("only http(s) URLs with a hostname are allowed")
    if parsed.username or parsed.password:
        raise BrowserSafetyError("URLs containing embedded credentials are blocked")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise BrowserSafetyError("local destinations are blocked")
    if settings.browser_block_private_networks:
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise BrowserSafetyError("destination hostname could not be resolved") from exc
        if not addresses or any(_is_blocked_ip(address) for address in addresses):
            raise BrowserSafetyError("private or otherwise unsafe network destinations are blocked")
    return url.strip()


async def _guard_request(route: Route, request: Request) -> None:
    try:
        validate_navigation_url(request.url)
    except BrowserSafetyError:
        await route.abort("blockedbyclient")
        return
    await route.continue_()


async def _get_playwright() -> Playwright:
    global _PLAYWRIGHT
    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = await async_playwright().start()
    return _PLAYWRIGHT


async def _close_session(session: BrowserSession) -> None:
    await session.context.close()
    await session.browser.close()
    _SESSIONS.pop(session.session_id, None)


async def create_session(user_id: str, url: str) -> BrowserSession:
    safe_url = validate_navigation_url(url)
    async with _LOCK:
        user_sessions = [s for s in _SESSIONS.values() if s.user_id == user_id]
        if len(user_sessions) >= settings.browser_max_sessions_per_user:
            raise BrowserSafetyError("maximum active browser sessions reached")
        pw = await _get_playwright()
        browser = await pw.chromium.launch(headless=settings.browser_headless)
        context = await browser.new_context(
            java_script_enabled=True,
            accept_downloads=False,
            permissions=[],
            service_workers="block",
        )
        await context.route("**/*", _guard_request)
        page = await context.new_page()
        page.set_default_timeout(settings.browser_timeout_ms)
        page.set_default_navigation_timeout(settings.browser_navigation_timeout_ms)
        session = BrowserSession(uuid.uuid4().hex, user_id, browser, context, page, time.time(), time.time())
        _SESSIONS[session.session_id] = session
        try:
            await page.goto(safe_url, wait_until="domcontentloaded")
            validate_navigation_url(page.url)
        except Exception:
            await _close_session(session)
            raise
        return session


def get_session(session_id: str, user_id: str) -> BrowserSession:
    session = _SESSIONS.get(session_id)
    if session is None or session.user_id != user_id:
        raise BrowserSessionNotFound(session_id)
    session.last_used_at = time.time()
    return session


async def inspect_session(session: BrowserSession) -> dict:
    page = session.page
    title = await page.title()
    url = page.url
    validate_navigation_url(url)
    controls = await page.locator("input, textarea, select, button").evaluate_all(
        """els => els.slice(0, 200).map((el, index) => ({
            index,
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') || null,
            name: el.getAttribute('name') || null,
            id: el.id || null,
            autocomplete: el.getAttribute('autocomplete') || null,
            placeholder: el.getAttribute('placeholder') || null,
            ariaLabel: el.getAttribute('aria-label') || null,
            required: el.hasAttribute('required'),
            disabled: el.hasAttribute('disabled'),
            text: (el.innerText || el.value || '').slice(0, 120)
        }))"""
    )
    forms = await page.locator("form").evaluate_all(
        """forms => forms.slice(0, 50).map((form, index) => ({
            index,
            action: form.getAttribute('action') || null,
            method: (form.getAttribute('method') || 'get').toLowerCase(),
            fields: form.querySelectorAll('input,textarea,select').length
        }))"""
    )
    return {
        "url": url,
        "title": title[:500],
        "forms": forms,
        "controls": controls,
        "submission_allowed": False,
        "warnings": [
            "Page inspection is read-only in Phase 6.",
            "CAPTCHA and anti-bot controls must not be bypassed.",
            "OTP, payment, legal declarations and final submission require explicit approval in later safety phases.",
        ],
    }


async def navigate_session(session: BrowserSession, url: str) -> dict:
    safe_url = validate_navigation_url(url)
    response = await session.page.goto(safe_url, wait_until="domcontentloaded")
    final_url = validate_navigation_url(session.page.url)
    return {"status": "ok", "url": final_url, "http_status": response.status if response else None}


async def screenshot_session(session: BrowserSession) -> bytes:
    if not settings.browser_screenshot_enabled:
        raise BrowserSafetyError("browser screenshots are disabled")
    return await session.page.screenshot(type="png", full_page=True)


async def close_session(session_id: str, user_id: str) -> None:
    session = get_session(session_id, user_id)
    async with _LOCK:
        await _close_session(session)


async def close_all_sessions() -> None:
    async with _LOCK:
        for session in list(_SESSIONS.values()):
            await _close_session(session)
        global _PLAYWRIGHT
        if _PLAYWRIGHT is not None:
            await _PLAYWRIGHT.stop()
            _PLAYWRIGHT = None
