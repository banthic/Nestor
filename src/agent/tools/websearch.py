"""Web search tool using DuckDuckGo HTML."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _web_search(query: str, max_results: int = 5) -> str:
    if not query or not str(query).strip():
        return "Query is required."

    max_results = max(1, min(int(max_results), 10))
    url = "https://html.duckduckgo.com/html/"

    try:
        with httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            resp = client.post(url, data={"q": query})
            resp.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        return f"Search failed: {exc}"

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for result in soup.select(".result__body")[:max_results]:
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.get("href") or ""
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        if link:
            results.append(f"- {title}\n  {link}\n  {snippet}")

    if not results:
        return "No results found."

    return "\n\n".join(results)


web_search = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo. Returns titles, URLs and snippets. "
            "Use to find up-to-date information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results (1-10). Defaults to 5.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
    "call": _web_search,
}
