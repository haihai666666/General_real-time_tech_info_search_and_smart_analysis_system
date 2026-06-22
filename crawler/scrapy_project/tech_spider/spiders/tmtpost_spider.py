"""钛媒体爬虫 - RSS/列表页优先"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class TmtpostSpider(BaseTechSpider):
    name = "tmtpost"
    allowed_domains = ["tmtpost.com", "www.tmtpost.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    FEED_URLS = [
        "https://www.tmtpost.com/feed",
        "https://www.tmtpost.com/nictation",
    ]

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        for url in self.FEED_URLS:
            yield scrapy.Request(url, callback=self.parse_feed_or_list, errback=self.errback_handler, dont_filter=True)

    def parse_feed_or_list(self, response):
        items = response.xpath("//item")
        if items:
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
                        source="tmtpost",
                        category="tech_business",
                        language="zh",
                        tags=["钛媒体", "科技产业"],
                        extra={"source_mode": "rss"},
                    )
            return

        links = response.css("a::attr(href)").getall()
        seen = set()
        for href in links:
            if not href or not href.startswith("http"):
                continue
            if "tmtpost.com" not in href or href in seen:
                continue
            seen.add(href)
            yield scrapy.Request(href, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        title = response.css("h1::text, meta[property='og:title']::attr(content)").get("").strip()
        content = " ".join(response.css("article p::text, .content p::text, p::text").getall())
        if len(content) < 30:
            content = response.css("meta[property='og:description']::attr(content)").get("").strip()
        if title and content:
            yield self.make_article(
                title=title,
                content=content,
                summary=content[:300],
                url=response.url,
                published_at=datetime.now(timezone.utc).isoformat(),
                source="tmtpost",
                category="tech_business",
                language="zh",
                tags=["钛媒体", "科技产业"],
            )
