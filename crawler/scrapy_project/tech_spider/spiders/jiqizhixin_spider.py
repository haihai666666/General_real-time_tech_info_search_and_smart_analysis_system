"""机器之心 AI 资讯爬虫 - RSS 优先，网页兜底"""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class JiqizhixinSpider(BaseTechSpider):
    name = "jiqizhixin"
    allowed_domains = ["jiqizhixin.com", "www.jiqizhixin.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, max_results=30, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)
        self._emitted = 0

    def start_requests(self):
        rss_url = "https://www.jiqizhixin.com/rss"
        yield scrapy.Request(
            rss_url,
            callback=self.parse_rss,
            errback=self.errback_handler,
            dont_filter=True,
        )

    def parse_rss(self, response):
        """解析 RSS，若失效则回退到网页抓取"""
        body = (response.text or "").lower()
        items = response.xpath("//item")[: self.max_results]

        if items and ("<rss" in body or "<item" in body):
            logger.info("Jiqizhixin RSS available: found %d items", len(items))
            for item in items:
                title = item.xpath("title/text()").get("").strip()
                link = item.xpath("link/text()").get("").strip()
                description = item.xpath("description/text()").get("").strip()
                pub_date = item.xpath("pubDate/text()").get("")
                categories = item.xpath("category/text()").getall()
                creator = item.xpath("*[local-name()='creator']/text()").get("")
                authors = [creator] if creator else []

                yield self.make_article(
                    title=title,
                    content=description,
                    summary=description[:300] if description else "",
                    url=link,
                    published_at=pub_date,
                    source="jiqizhixin",
                    category="ai_ml",
                    language="zh",
                    authors=authors,
                    tags=categories[:5] if categories else ["AI", "机器学习"],
                    extra={"source_mode": "rss"},
                )
            return

        logger.warning(
            "Jiqizhixin RSS unavailable or not XML. status=%s, content_type=%s. Fallback to homepage parsing.",
            response.status,
            response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore"),
        )

        yield scrapy.Request(
            "https://www.jiqizhixin.com/",
            callback=self.parse_homepage,
            errback=self.errback_handler,
            dont_filter=True,
        )

    def parse_homepage(self, response):
        """从首页提取文章链接（宽松兜底）"""
        raw_links = response.css("a::attr(href)").getall()

        normalized = []
        for href in raw_links:
            if not href:
                continue
            href = href.strip()
            if href.startswith("javascript:") or href.startswith("#"):
                continue
            full = urljoin(response.url, href)
            if "jiqizhixin.com" not in full:
                continue
            normalized.append(full)

        blacklist_keywords = [
            "/tag", "/topic", "/author", "/about", "/contact", "/login",
            "/register", "/privacy", "/terms", "/search", "/sitemap",
        ]

        candidates = []
        seen = set()
        for link in normalized:
            lower = link.lower()
            if any(k in lower for k in blacklist_keywords):
                continue
            path = link.replace("https://", "").replace("http://", "").split("/", 1)
            if len(path) < 2 or len(path[1].strip("/")) < 6:
                continue
            if link in seen:
                continue
            seen.add(link)
            candidates.append(link)

        if len(candidates) < 3:
            import re

            text_urls = re.findall(r"https?://(?:www\.)?jiqizhixin\.com/[^\"'\s<>]+", response.text)
            for link in text_urls:
                lower = link.lower()
                if any(k in lower for k in blacklist_keywords):
                    continue
                if link in seen:
                    continue
                seen.add(link)
                candidates.append(link)

        article_urls = candidates[: self.max_results]

        if not article_urls:
            logger.warning("Jiqizhixin homepage fallback found 0 candidate links")
            return

        logger.info("Jiqizhixin homepage fallback found %d candidate links", len(article_urls))
        for url in article_urls:
            yield scrapy.Request(url, callback=self.parse_article, errback=self.errback_handler)

    def parse_article(self, response):
        """解析文章详情（兜底方案）"""
        if self._emitted >= self.max_results:
            return

        title = (
            response.css("h1::text").get()
            or response.css("meta[property='og:title']::attr(content)").get()
            or response.css("meta[name='twitter:title']::attr(content)").get()
            or response.css("title::text").get("")
        ).strip()

        paragraphs = response.css("article p::text, .article p::text, .content p::text, p::text").getall()
        content = "\n".join([p.strip() for p in paragraphs if p and p.strip()])

        if len(content) < 40:
            meta_desc = (
                response.css("meta[property='og:description']::attr(content)").get()
                or response.css("meta[name='description']::attr(content)").get("")
            ).strip()
            if meta_desc:
                content = meta_desc

        if not title or len(content) < 20:
            logger.debug("Skip candidate due to weak content: %s", response.url)
            return

        self._emitted += 1
        yield self.make_article(
            title=title,
            content=content,
            summary=content[:300],
            url=response.url,
            published_at=datetime.now(timezone.utc).isoformat(),
            source="jiqizhixin",
            category="ai_ml",
            language="zh",
            tags=["AI", "机器学习"],
            extra={"source_mode": "homepage_fallback"},
        )
