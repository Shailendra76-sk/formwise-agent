from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus, urlparse

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
        "source": str(item.get("source") or "web_search"),
    }


def _ddg_results(html: str, max_results: int) -> list[dict[str, str]]:
    results=[]
    pattern=re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',re.I|re.S)
    for url,title in pattern.findall(html):
        clean_title=re.sub(r"<[^>]+>","",unescape(title)).strip()
        clean_url=unescape(url)
        if clean_url.startswith("//duckduckgo.com/l/?") and "uddg=" in clean_url:
            from urllib.parse import parse_qs
            clean_url=parse_qs(urlparse(clean_url).query).get("uddg",[clean_url])[0]
        results.append(_clean_result({"title":clean_title,"url":clean_url,"source":"duckduckgo"}))
        if len(results)>=max_results: break
    return results


async def search_web(query: str, *, official_only: bool = True, max_results: int = 8) -> dict[str, Any]:
    """Current web research with an optional Serper provider and public-search fallback."""
    if settings.serper_api_key:
        headers={"X-API-KEY":settings.serper_api_key,"Content-Type":"application/json"}
        payload={"q":query,"num":max_results}
        async with httpx.AsyncClient(timeout=settings.research_timeout_seconds,follow_redirects=True) as client:
            response=await client.post(settings.serper_url,headers=headers,json=payload)
            response.raise_for_status(); data=response.json()
        results=[_clean_result(x) for x in data.get("organic",[])]
        if official_only: results=[x for x in results if _allowed_url(x["url"])]
        return {"status":"ok","query":query,"results":results[:max_results],"provider":"serper"}
    try:
        url="https://html.duckduckgo.com/html/?q="+quote_plus(query)
        async with httpx.AsyncClient(timeout=settings.research_timeout_seconds,follow_redirects=True,headers={"User-Agent":"FormwiseAgent/1.0"}) as client:
            response=await client.get(url); response.raise_for_status()
        results=_ddg_results(response.text,max_results*2)
        if official_only: results=[x for x in results if _allowed_url(x["url"])][:max_results]
        else: results=results[:max_results]
        return {"status":"ok","query":query,"results":results,"provider":"duckduckgo"}
    except httpx.HTTPError as exc:
        return {"status":"unavailable","query":query,"results":[],"message":f"Web research failed: {exc.__class__.__name__}"}


async def research_exam(exam_name: str, year: int) -> dict[str, Any]:
    query=f"site:ssc.gov.in {exam_name} {year} notification eligibility application dates fee"
    result=await search_web(query,official_only=True,max_results=10)
    results=result.get("results",[])
    notification=next((x for x in results if any(t in x["title"].lower() for t in ("notice","notification","combined higher secondary"))),None)
    apply_url=next((x["url"] for x in results if _allowed_url(x["url"])),"https://ssc.gov.in/")
    return {"status":result["status"],"exam":exam_name,"year":year,"notification_found":notification is not None,"notification":notification,"apply_url":apply_url,"sources":results,"message":result.get("message"),"provider":result.get("provider"),"must_verify_before_submission":True}
