"""爱范儿科技资讯爬虫 - 通过 RSS 获取最新消费科技资讯"""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class IfanrSpider(BaseTechSpider):
    name = "ifanr"
    allowed_domains = ["ifanr.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, max_results=30, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        # 爱范儿 RSS feed
        rss_url = "https://www.ifanr.com/feed"
        yield scrapy.Request(rss_url, callback=self.parse_rss, errback=self.errback_handler)

    def parse_rss(self, response):
        """解析 RSS feed"""
        items = response.xpath("//item")[:self.max_results]
        logger.info("Ifanr: found %d items", len(items))

        for item in items:
            title = item.xpath("title/text()").get("").strip()
            link = item.xpath("link/text()").get("").strip()
            description = item.xpath("description/text()").get("").strip()
            pub_date = item.xpath("pubDate/text()").get("")
            
            # 提取分类
            categories = item.xpath("category/text()").getall()
            
            # 提取作者
            creator = item.xpath("*[local-name()='creator']/text()").get("")
            authors = [creator] if creator else []

            yield self.make_article(
                title=title,
                content=description,
                summary=description[:300] if description else "",
                url=link,
                published_at=pub_date,
                source="ifanr",
                category="consumer_tech",
                language="zh",
                authors=authors,
                tags=categories[:5] if categories else ["科技", "消费电子"],
                extra={"rss_feed": "ifanr"},
            )
