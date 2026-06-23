"""基础爬虫类，提供通用的解析和错误处理逻辑"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class BaseTechSpider(scrapy.Spider):
    """所有科技信息爬虫的基类"""

    custom_settings = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crawl_start_time = datetime.now(timezone.utc)
        self.item_count = 0
        self.error_count = 0

    def errback_handler(self, failure):
        """通用错误处理"""
        self.error_count += 1
        logger.error(
            "[%s] Request failed: %s - %s",
            self.name,
            failure.request.url,
            failure.getErrorMessage(),
        )

    def make_article(self, **kwargs):
        """构造标准文章item"""
        from tech_spider.items import TechArticleItem

        item = TechArticleItem()
        item["source"] = kwargs.get("source", self.name)
        item["crawled_at"] = datetime.now(timezone.utc).isoformat()
        item["language"] = kwargs.get("language", "en")
        item["category"] = kwargs.get("category", "general")
        item["tags"] = kwargs.get("tags", [])
        item["authors"] = kwargs.get("authors", [])
        item["extra"] = kwargs.get("extra", {})
        for field in ("title", "content", "summary", "url", "published_at", "raw_html"):
            if field in kwargs:
                item[field] = kwargs[field]
        self.item_count += 1
        return item
