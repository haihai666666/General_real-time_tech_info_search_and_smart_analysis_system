"""MIT News 爬虫 - 抓取 MIT 科技新闻"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class MitNewsSpider(BaseTechSpider):
    name = "mit_news"
    allowed_domains = ["news.mit.edu"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    TOPIC_URLS = [
        "https://news.mit.edu/topic/artificial-intelligence2",
        "https://news.mit.edu/topic/computers",
        "https://news.mit.edu/topic/robotics",
        "https://news.mit.edu/topic/data",
    ]

    def start_requests(self):
        for url in self.TOPIC_URLS:
            yield scrapy.Request(url, callback=self.parse_list, errback=self.errback_handler)

    def parse_list(self, response):
        article_links = response.css("h3.news-card--title a::attr(href)").getall()
        if not article_links:
            article_links = response.css("a.news-card--link::attr(href)").getall()
        logger.info("MIT News: found %d article links on %s", len(article_links), response.url)
        for link in article_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        title = response.css("h1.article-title::text").get("")
        if not title:
            title = response.css("h1::text").get("").strip()

        paragraphs = response.css("div.article-body p::text, div.article-body p *::text").getall()
        content = " ".join(p.strip() for p in paragraphs if p.strip())

        date_str = response.css("time::attr(datetime)").get("")
        if not date_str:
            date_str = response.css(".article-date::text").get("").strip()

        tags = response.css("a.article-tag::text").getall()
        tags = [t.strip() for t in tags if t.strip()]

        if title and content:
            yield self.make_article(
                title=title.strip(),
                content=content,
                summary=content[:500] if len(content) > 500 else content,
                url=response.url,
                published_at=date_str or datetime.now(timezone.utc).isoformat(),
                source="mit_news",
                category="research",
                tags=tags,
            )
