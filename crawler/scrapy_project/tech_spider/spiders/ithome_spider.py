"""ITHome crawler. Prefer RSS; use homepage only when RSS is unavailable."""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider
from tech_spider.spiders.feed_utils import extract_feed_entries
from tech_spider.spiders.url_utils import is_ithome_article_url

logger = logging.getLogger(__name__)


class IthomeSpider(BaseTechSpider):
    name = "ithome"
    allowed_domains = ["ithome.com", "www.ithome.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_TIMEOUT": 20,
    }

    def __init__(self, max_results=30, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        yield scrapy.Request(
            "https://www.ithome.com/rss/",
            callback=self.parse_rss,
            errback=self.errback_handler,
            dont_filter=True,
        )

    def parse_rss(self, response):
        entries = extract_feed_entries(response.text)
        logger.info("ITHome RSS: found %d entries", len(entries))
        if not entries:
            logger.warning("ITHome RSS yielded no entries; falling back to homepage")
            yield scrapy.Request(
                "https://www.ithome.com/",
                callback=self.parse_homepage,
                errback=self.errback_handler,
                dont_filter=True,
            )
            return

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
                published_at=entry["published_at"]
                or datetime.now(timezone.utc).isoformat(),
                source="ithome",
                category="tech_news_cn",
                language="zh",
                authors=entry["authors"],
                tags=entry["tags"][:5] if entry["tags"] else ["ITHome"],
                extra={"source_mode": "rss"},
            )

    def parse_homepage(self, response):
        links = response.css("a::attr(href)").getall()
        seen = set()
        for href in links:
            if self._emitted >= self.max_results:
                break
            full = urljoin(response.url, href or "")
            if not is_ithome_article_url(full) or full in seen:
                continue
            seen.add(full)
            yield scrapy.Request(
                full, callback=self.parse_article, errback=self.errback_handler
            )

    def parse_article(self, response):
        if self._emitted >= self.max_results:
            return
        title = (
            response.css("h1::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or response.css("title::text").get("")
        ).strip()
        paragraphs = response.css(
            "article p::text, .article p::text, .content p::text, p::text"
        ).getall()
        content = "\n".join(p.strip() for p in paragraphs if p and p.strip())
        if len(content) < 40:
            content = (
                response.css("meta[property='og:description']::attr(content)").get()
                or ""
            ).strip()
        if not title or len(content) < 20:
            logger.debug("ITHome skip weak page: %s", response.url)
            return

        self._emitted += 1
        yield self.make_article(
            title=title,
            content=content,
            summary=content[:300],
            url=response.url,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="ithome",
            category="tech_news_cn",
            language="zh",
            tags=["ITHome"],
            extra={"source_mode": "homepage_fallback"},
        )
