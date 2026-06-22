"""雷锋网爬虫 - RSS 优先"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class LeiphoneSpider(BaseTechSpider):
    name = "leiphone"
    allowed_domains = ["leiphone.com", "www.leiphone.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    FEED_URLS = ["https://www.leiphone.com/feed"]

    def __init__(self, max_results=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        for url in self.FEED_URLS:
            yield scrapy.Request(url, callback=self.parse_feed, errback=self.errback_handler, dont_filter=True)

    def parse_feed(self, response):
        items = response.xpath("//item")
        logger.info("Leiphone RSS: found %d items", len(items))
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
                    source="leiphone",
                    category="ai_hardware",
                    language="zh",
                    tags=["雷锋网", "AI", "智能硬件"],
                    extra={"source_mode": "rss"},
                )
