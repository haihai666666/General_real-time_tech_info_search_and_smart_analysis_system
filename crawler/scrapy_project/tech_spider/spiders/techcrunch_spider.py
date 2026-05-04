"""TechCrunch 爬虫 - 通过 RSS Feed 抓取科技新闻"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class TechCrunchSpider(BaseTechSpider):
    name = "techcrunch"
    allowed_domains = ["techcrunch.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    def start_requests(self):
        yield scrapy.Request(
            "https://techcrunch.com/feed/",
            callback=self.parse_feed,
            errback=self.errback_handler,
        )

    def parse_feed(self, response):
        items = response.xpath("//item")
        logger.info("TechCrunch RSS: found %d items", len(items))

        for item in items:
            title = item.xpath("title/text()").get("").strip()
            link = item.xpath("link/text()").get("").strip()
            pub_date = item.xpath("pubDate/text()").get("").strip()
            description = item.xpath("description/text()").get("").strip()
            categories = item.xpath("category/text()").getall()
            author = item.xpath("dc:creator/text()").get("").strip()

            if link:
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    errback=self.errback_handler,
                    meta={
                        "title": title,
                        "pub_date": pub_date,
                        "rss_description": description,
                        "categories": categories,
                        "author": author,
                    },
                )

    def parse_article(self, response):
        title = response.meta.get("title", "")
        paragraphs = response.css("div.article-content p::text, div.entry-content p::text, article p::text").getall()
        content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not content:
            content = response.meta.get("rss_description", "")

        if title and content:
            yield self.make_article(
                title=title,
                content=content,
                summary=content[:500] if len(content) > 500 else content,
                url=response.url,
                published_at=response.meta.get("pub_date", datetime.now(timezone.utc).isoformat()),
                source="techcrunch",
                category="tech_news",
                authors=[response.meta["author"]] if response.meta.get("author") else [],
                tags=response.meta.get("categories", []),
            )
