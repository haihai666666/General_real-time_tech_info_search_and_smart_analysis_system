"""月光博客爬虫 - RSS 优先，网页标题兜底"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class WilliamlongSpider(BaseTechSpider):
    name = "williamlong"
    allowed_domains = ["williamlong.info", "www.williamlong.info"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        yield scrapy.Request(
            "https://www.williamlong.info/rss.xml",
            callback=self.parse_rss,
            errback=self.errback_handler,
            dont_filter=True,
        )
        yield scrapy.Request(
            "https://www.williamlong.info/",
            callback=self.parse_homepage,
            errback=self.errback_handler,
            dont_filter=True,
        )

    def parse_rss(self, response):
        items = response.xpath("//item")
        logger.info("Williamlong RSS: found %d items", len(items))
        for item in items[: self.max_results]:
            title = item.xpath("title/text()").get("").strip()
            link = item.xpath("link/text()").get("").strip()
            description = item.xpath("description/text()").get("").strip()
            pub_date = item.xpath("pubDate/text()").get("").strip()
            if title and link:
                yield self.make_article(
                    title=title,
                    content=description or title,
                    summary=(description or title)[:300],
                    url=link,
                    published_at=pub_date or datetime.now(timezone.utc).isoformat(),
                    source="williamlong",
                    category="tech_commentary",
                    language="zh",
                    tags=["科技评论", "互联网"],
                    extra={"source_mode": "rss"},
                )

    def parse_homepage(self, response):
        links = response.css("a::attr(href)").getall()
        for href in links:
            if self._emitted >= self.max_results:
                break
            if (
                not href
                or not href.startswith("http")
                or "williamlong.info" not in href
            ):
                continue
            yield scrapy.Request(
                href, callback=self.parse_article, errback=self.errback_handler
            )

    def parse_article(self, response):
        if self._emitted >= self.max_results:
            return
        title = (
            response.css(
                "h1::text, meta[property='og:title']::attr(content), title::text"
            )
            .get("")
            .strip()
        )
        content = "\n".join(
            p.strip()
            for p in response.css(
                "article p::text, .post-content p::text, p::text"
            ).getall()
            if p.strip()
        )
        if len(content) < 40:
            content = (
                response.css("meta[name='description']::attr(content)").get() or ""
            ).strip()
        if not title or len(content) < 20:
            return
        self._emitted += 1
        yield self.make_article(
            title=title,
            content=content,
            summary=content[:300],
            url=response.url,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="williamlong",
            category="tech_commentary",
            language="zh",
            tags=["科技评论", "互联网"],
            extra={"source_mode": "homepage_fallback"},
        )
