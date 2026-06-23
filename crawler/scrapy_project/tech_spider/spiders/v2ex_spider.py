"""V2EX crawler using official Atom feeds."""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider
from tech_spider.spiders.feed_utils import extract_feed_entries

logger = logging.getLogger(__name__)


class V2exSpider(BaseTechSpider):
    name = "v2ex"
    allowed_domains = ["v2ex.com", "www.v2ex.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    FEEDS = [
        "https://www.v2ex.com/feed/tab/tech.xml",
        "https://www.v2ex.com/feed/programmer.xml",
        "https://www.v2ex.com/feed/python.xml",
    ]

    def __init__(self, max_results=30, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        for url in self.FEEDS:
            yield scrapy.Request(
                url,
                callback=self.parse_feed,
                errback=self.errback_handler,
                dont_filter=True,
            )

    def parse_feed(self, response):
        entries = extract_feed_entries(response.text)
        logger.info("V2EX feed: found %d entries from %s", len(entries), response.url)
        if not entries:
            logger.warning(
                "V2EX feed yielded no entries: %s (%d bytes)",
                response.url,
                len(response.body),
            )

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
                source="v2ex",
                category="community",
                language="zh",
                authors=entry["authors"],
                tags=entry["tags"][:5] if entry["tags"] else ["V2EX", "programmer"],
                extra={"source_mode": "atom_feed"},
            )
