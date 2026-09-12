from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings

OFFICIAL_DOMAINS = {"ssc.gov.in", "www.ssc.gov.in"}


def _allowed_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host in OFFICIAL_DOMAINS or host.endswith(".gov.in")


def _clean_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or "")[:500],
        "url": str(item.get("link") or item.get("url") or "")[:2048],
        "snippet": str(item.get("snippet") or item.get("description") or "")[:1200],
        "source": "web_search",
    }


async def search_web(query: str, *, official_only: bool = True, max_results: int = 8) -> dict[str, Any]:
    """Search current web information through a configured Serper endpoint.

    No search result is fabricated when the provider is unavailable. For SSC tasks,
    official SSC/Government domains are preferred and non-official results are marked.
    """
    if not settings.serper_api_key:
        return {"status": "unavailable", "query": query, "results": [], "message": "Web research provider is not configured. Set FORMWISE_SERPER_API_KEY."}
    headers = {"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": max_results}
    async with httpx.AsyncClient(timeout=settings.research_timeout_seconds, follow_redirects=True) as client:
        response = await client.post(settings.serper_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    results = [_clean_result(x) for x in data.get("organic", [])]
    if official_only:
        results = [x for x in results if _allowed_url(x["url"])]
    return {"status": "ok", "query": query, "results": results[:max_results]}


async def research_exam(exam_name: str, year: int) -> dict[str, Any]:
    query = f"site:ssc.gov.in {exam_name} {year} notification eligibility application dates fee"
    result = await search_web(query, official_only=True, max_results=10)
    results = result.get("results", [])
    notification = next((x for x in results if "notice" in x["title"].lower() or "notification" in x["title"].lower()), None)
    apply_url = next((x["url"] for x in results if "/ssc.gov.in" in x["url"] or "ssc.gov.in" in x["url"]), "https://ssc.gov.in/")
    return {
        "status": result["status"],
        "exam": exam_name,
        "year": year,
        "notification_found": notification is not None,
        "notification": notification,
        "apply_url": apply_url,
        "sources": results,
        "message": result.get("message"),
        "must_verify_before_submission": True,
    }
