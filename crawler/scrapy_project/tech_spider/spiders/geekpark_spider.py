"""GeekPark crawler with feed parsing and homepage fallback."""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider
from tech_spider.spiders.feed_utils import extract_feed_entries
from tech_spider.spiders.url_utils import is_geekpark_article_url

logger = logging.getLogger(__name__)

GEEKPARK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


class GeekparkSpider(BaseTechSpider):
    name = "geekpark"
    allowed_domains = ["geekpark.net", "www.geekpark.net"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_TIMEOUT": 20,
        "RETRY_TIMES": 2,
        "DEFAULT_REQUEST_HEADERS": GEEKPARK_HEADERS,
        "DOWNLOADER_MIDDLEWARES": {
            "tech_spider.middlewares.RandomUserAgentMiddleware": None,
            "tech_spider.middlewares.RetryWithLoggingMiddleware": 550,
        },
    }

    FEED_URLS = ["https://www.geekpark.net/rss"]

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        yield scrapy.Request(
            "https://www.geekpark.net/",
            callback=self.parse_list,
            errback=self.errback_handler,
            headers=GEEKPARK_HEADERS,
            dont_filter=True,
        )

    def parse_feed(self, response):
        entries = extract_feed_entries(response.text)
        logger.info(
            "GeekPark feed: found %d entries from %s", len(entries), response.url
        )
        if not entries:
            logger.warning(
                "GeekPark feed yielded no entries: %s (%d bytes)",
                response.url,
                len(response.body),
            )
            yield scrapy.Request(
                "https://www.geekpark.net/",
                callback=self.parse_list,
                errback=self.errback_handler,
                headers=GEEKPARK_HEADERS,
                dont_filter=True,
            )
            return

        for entry in entries:
            if self._emitted >= self.max_results:
                break
            content = entry["content"] or entry["summary"] or entry["title"]
            self._emitted += 1
            yield self.make_article(
                title=entry["title"],
                content=content,
                summary=(entry["summary"] or content)[:300],
                url=entry["link"],
                published_at=entry["published_at"]
                or datetime.now(timezone.utc).isoformat(),
                source="geekpark",
                category="tech_insight",
                language="zh",
                tags=entry["tags"][:5]
                if entry["tags"]
                else ["geekpark", "tech_insight"],
                extra={"source_mode": "rss"},
            )

    def parse_list(self, response):
        seen = set()
        hrefs = response.css("a::attr(href)").getall()
        hrefs.extend(
            re.findall(
                r"""["']((?:https?://www\.geekpark\.net)?/news/\d+)["']""",
                response.text,
            )
        )
        logger.info("GeekPark homepage: found %d candidate links", len(hrefs))

        for href in hrefs:
            if self._emitted >= self.max_results:
                break
            full = urljoin(response.url, href or "")
            if not is_geekpark_article_url(full) or full in seen:
                continue
            seen.add(full)
            yield scrapy.Request(
                full,
                callback=self.parse_article,
                errback=self.errback_handler,
                headers=GEEKPARK_HEADERS,
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
            "article p::text, .article-content p::text, .post-content p::text, p::text"
        ).getall()
        content = "\n".join(p.strip() for p in paragraphs if p and p.strip())
        if len(content) < 30:
            content = (
                response.css("meta[property='og:description']::attr(content)").get()
                or ""
            ).strip()
        if not title or not content:
            logger.debug("GeekPark skip weak page: %s", response.url)
            return

        self._emitted += 1
        yield self.make_article(
            title=title,
            content=content,
            summary=content[:300],
            url=response.url,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="geekpark",
            category="tech_insight",
            language="zh",
            tags=["geekpark", "tech_insight"],
            extra={"source_mode": "homepage_fallback"},
        )
