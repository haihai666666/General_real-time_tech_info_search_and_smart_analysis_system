"""IEEE Spectrum 爬虫 - 抓取 IEEE 科技资讯"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class IeeeSpectrumSpider(BaseTechSpider):
    name = "ieee_spectrum"
    allowed_domains = ["spectrum.ieee.org"]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
    }

    START_URLS = [
        "https://spectrum.ieee.org/topic/artificial-intelligence/",
        "https://spectrum.ieee.org/topic/computing/",
        "https://spectrum.ieee.org/topic/robotics/",
        "https://spectrum.ieee.org/topic/semiconductors/",
    ]

    def start_requests(self):
        for url in self.START_URLS:
            yield scrapy.Request(url, callback=self.parse_list, errback=self.errback_handler)

    def parse_list(self, response):
        links = response.css("h2 a::attr(href), h3 a::attr(href)").getall()
        if not links:
            links = response.css("a.article-title::attr(href)").getall()
        logger.info("IEEE Spectrum: found %d links on %s", len(links), response.url)
        for link in links[:20]:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        title = response.css("h1::text").get("").strip()
        paragraphs = response.css("article p::text, article p *::text").getall()
        content = " ".join(p.strip() for p in paragraphs if p.strip())

        date_str = response.css("time::attr(datetime)").get("")
        if not date_str:
            date_str = response.css("meta[property='article:published_time']::attr(content)").get("")

        author = response.css("a[rel='author']::text").get("").strip()
        tags = response.css("a.tag::text, meta[name='keywords']::attr(content)").getall()
        tags = [t.strip() for t in tags if t.strip()]

        if title and content:
            yield self.make_article(
                title=title,
                content=content,
                summary=content[:500] if len(content) > 500 else content,
                url=response.url,
                published_at=date_str or datetime.now(timezone.utc).isoformat(),
                source="ieee_spectrum",
                category="technology",
                authors=[author] if author else [],
                tags=tags,
            )
