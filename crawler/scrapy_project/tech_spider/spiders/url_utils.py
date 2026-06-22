"""URL filtering helpers for spider link fallbacks."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_GEEKPARK_NEWS_RE = re.compile(r"^/news/\d+/?$")
_ITHOME_ARTICLE_RE = re.compile(r"^/\d+/\d+/\d+\.htm$")


def is_geekpark_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"www.geekpark.net", "geekpark.net"} and bool(
        _GEEKPARK_NEWS_RE.match(parsed.path)
    )


def is_ithome_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"www.ithome.com", "ithome.com"} and bool(
        _ITHOME_ARTICLE_RE.match(parsed.path)
    )
