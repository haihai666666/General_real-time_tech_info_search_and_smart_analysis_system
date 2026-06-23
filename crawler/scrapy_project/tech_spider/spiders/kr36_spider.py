"""36氪科技新闻爬虫 - 通过 RSS 获取最新科技资讯"""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class Kr36Spider(BaseTechSpider):
    name = "36kr"
    allowed_domains = ["36kr.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, max_results=30, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        # 36氪 RSS feed
        rss_url = "https://36kr.com/feed"
        yield scrapy.Request(
            rss_url, callback=self.parse_rss, errback=self.errback_handler
        )

    def parse_rss(self, response):
        """解析 RSS feed"""
        items = response.xpath("//item")[: self.max_results]
        logger.info("36kr: found %d items", len(items))

        for item in items:
            title = item.xpath("title/text()").get("").strip()
            link = item.xpath("link/text()").get("").strip()
            description = item.xpath("description/text()").get("").strip()
            pub_date = item.xpath("pubDate/text()").get("")

            # 解析分类
            categories = item.xpath("category/text()").getall()

            # 提取作者（如果有）
            creator = item.xpath("*[local-name()='creator']/text()").get("")
            authors = [creator] if creator else []

            yield self.make_article(
                title=title,
                content=description,
                summary=description[:300] if description else "",
                url=link,
                published_at=pub_date,
                source="36kr",
                category="tech_news",
                language="zh",
                authors=authors,
                tags=categories[:5],
                extra={"rss_feed": "36kr"},
            )

    def parse(self, response):
        """备用：直接爬取网页（如果 RSS 不可用）"""
        articles = response.css("div.article-item")
        logger.info("36kr: found %d articles on page", len(articles))

        for article in articles[: self.max_results]:
            title = article.css("h3::text, h2::text").get("").strip()
            link = article.css("a::attr(href)").get("")
            if link:
                link = urljoin(response.url, link)

            summary = article.css("p.summary::text, div.desc::text").get("").strip()

            yield self.make_article(
                title=title,
                content=summary,
                summary=summary[:300] if summary else "",
                url=link,
                published_at=datetime.now(timezone.utc).isoformat(),
                source="36kr",
                category="tech_news",
                language="zh",
                tags=["科技", "创投"],
            )
