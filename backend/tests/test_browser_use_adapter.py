import pytest

from app.browser_use_agent import BrowserUseUnavailable, run_browser_use_task


@pytest.mark.asyncio
async def test_browser_use_adapter_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("FORMWISE_BROWSER_USE_ENABLED", raising=False)
    with pytest.raises(BrowserUseUnavailable):
        await run_browser_use_task("inspect the form", allowed_url="https://example.com/form")


@pytest.mark.asyncio
async def test_browser_use_adapter_requires_url(monkeypatch):
    monkeypatch.setenv("FORMWISE_BROWSER_USE_ENABLED", "true")
    with pytest.raises(ValueError):
        await run_browser_use_task("inspect the form")
