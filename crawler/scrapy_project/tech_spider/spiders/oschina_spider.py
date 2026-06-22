"""开源中国爬虫 - RSS 优先，网页兜底"""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class OschinaSpider(BaseTechSpider):
    name = "oschina"
    allowed_domains = ["oschina.net", "www.oschina.net"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    FEED_URLS = [
        "https://www.oschina.net/news/rss",
        "https://www.oschina.net/project/rss",
    ]

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        for url in self.FEED_URLS:
            yield scrapy.Request(url, callback=self.parse_feed, errback=self.errback_handler, dont_filter=True)
        yield scrapy.Request("https://www.oschina.net/news", callback=self.parse_news_list, errback=self.errback_handler, dont_filter=True)

    def parse_feed(self, response):
        items = response.xpath("//item")
        logger.info("OSChina RSS: found %d items from %s", len(items), response.url)
        for item in items[: self.max_results]:
            title = item.xpath("title/text()").get("").strip()
            link = item.xpath("link/text()").get("").strip()
            description = item.xpath("description/text()").get("").strip()
            pub_date = item.xpath("pubDate/text()").get("").strip()
            creator = item.xpath("*[local-name()='creator']/text()").get("").strip()
            categories = item.xpath("category/text()").getall()
            if title and link:
                yield self.make_article(
                    title=title,
                    content=description or title,
                    summary=(description or title)[:300],
                    url=link,
                    published_at=pub_date or datetime.now(timezone.utc).isoformat(),
                    source="oschina",
                    category="open_source",
                    language="zh",
                    authors=[creator] if creator else [],
                    tags=categories[:5] if categories else ["开源中国", "开源"],
                    extra={"source_mode": "rss"},
                )

    def parse_news_list(self, response):
        links = response.css("a::attr(href)").getall()
        seen = set()
        count = 0
        for href in links:
            if count >= self.max_results:
                break
            if not href:
                continue
            full = urljoin(response.url, href)
            if "oschina.net" not in full or full in seen:
                continue
            if any(x in full for x in ["/tag/", "/search", "/project/", "/people/", "/event/"]):
                continue
            seen.add(full)
            count += 1
            yield scrapy.Request(full, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        title = (
            response.css("h1::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or response.css("title::text").get("")
        ).strip()
        content = "\n".join([p.strip() for p in response.css("article p::text, .article p::text, .news-content p::text, p::text").getall() if p.strip()])
        if len(content) < 50:
            content = (response.css("meta[property='og:description']::attr(content)").get() or "").strip()
        if title and content:
            yield self.make_article(
                title=title,
                content=content,
                summary=content[:300],
                url=response.url,
                published_at=datetime.now(timezone.utc).isoformat(),
                source="oschina",
                category="open_source",
                language="zh",
                tags=["开源中国", "开源"],
                extra={"source_mode": "web_fallback"},
            )
