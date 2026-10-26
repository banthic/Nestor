"""Web fetch tool."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _web_fetch(url: str, max_length: int = 4000) -> str:
    if not url or not str(url).strip():
        return "URL is required."

    max_length = max(500, min(int(max_length), 8000))

    try:
        with httpx.Client(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        return f"Fetch failed: {exc}"

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
    elif "application/json" in content_type:
        text = resp.text
    else:
        text = resp.text

    if len(text) > max_length:
        text = text[:max_length] + "\n\n[truncated]"
    return text


web_fetch = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Fetch a URL and return readable text content (truncated).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch.",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Max characters to return (500-8000). Defaults to 4000.",
                    "minimum": 500,
                    "maximum": 8000,
                },
            },
            "required": ["url"],
        },
    },
    "call": _web_fetch,
}
