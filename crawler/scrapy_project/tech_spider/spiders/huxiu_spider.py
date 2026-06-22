"""Huxiu crawler using the current RSS endpoint plus a homepage fallback."""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider
from tech_spider.spiders.feed_utils import extract_feed_entries

logger = logging.getLogger(__name__)


class HuxiuSpider(BaseTechSpider):
    name = "huxiu"
    allowed_domains = ["huxiu.com", "www.huxiu.com", "rss.huxiu.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    FEED_URLS = ["https://rss.huxiu.com/"]

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        for url in self.FEED_URLS:
            yield scrapy.Request(url, callback=self.parse_feed, errback=self.errback_handler, dont_filter=True)
        yield scrapy.Request("https://www.huxiu.com/", callback=self.parse_list, errback=self.errback_handler, dont_filter=True)

    def parse_feed(self, response):
        entries = extract_feed_entries(response.text)
        logger.info("Huxiu RSS: found %d entries from %s", len(entries), response.url)
        if not entries:
            logger.warning("Huxiu RSS yielded no entries: %s (%d bytes)", response.url, len(response.body))

        for entry in entries:
            if self._emitted >= self.max_results:
                break
            content = entry["content"] or entry["title"]
            self._emitted += 1
            yield self.make_article(
                title=entry["title"],
                content=content,
                summary=(entry["summary"] or content)[:300],
                url=entry["link"],
                published_at=entry["published_at"] or datetime.now(timezone.utc).isoformat(),
                source="huxiu",
                category="tech_business",
                language="zh",
                tags=entry["tags"][:5] if entry["tags"] else ["huxiu", "tech_business"],
                extra={"source_mode": "rss"},
            )

    def parse_list(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            if self._emitted >= self.max_results:
                break
            full = urljoin(response.url, href or "")
            parsed = urlparse(full)
            if parsed.netloc not in {"www.huxiu.com", "huxiu.com"}:
                continue
            if "/article/" not in parsed.path or not parsed.path.endswith(".html"):
                continue
            if full in seen:
                continue
            seen.add(full)
            yield scrapy.Request(full, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        if self._emitted >= self.max_results:
            return
        title = (
            response.css("h1::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or response.css("title::text").get("")
        ).strip()
        paragraphs = response.css("article p::text, .article-content p::text, .article-wrap p::text, p::text").getall()
        content = "\n".join(p.strip() for p in paragraphs if p and p.strip())
        if len(content) < 30:
            content = (response.css("meta[property='og:description']::attr(content)").get() or "").strip()
        if not title or not content:
            logger.debug("Huxiu skip weak page: %s", response.url)
            return

        self._emitted += 1
        yield self.make_article(
            title=title,
            content=content,
            summary=content[:300],
            url=response.url,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="huxiu",
            category="tech_business",
            language="zh",
            tags=["huxiu", "tech_business"],
            extra={"source_mode": "homepage_fallback"},
        )
