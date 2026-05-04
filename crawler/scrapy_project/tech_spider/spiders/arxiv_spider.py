"""ArXiv 论文爬虫 - 通过 Atom API 获取最新 CS 领域论文"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)

ARXIV_CATEGORIES = [
    "cs.AI",   # Artificial Intelligence
    "cs.LG",   # Machine Learning
    "cs.CL",   # Computation and Language (NLP)
    "cs.CV",   # Computer Vision
    "cs.SE",   # Software Engineering
    "cs.CR",   # Cryptography and Security
    "cs.RO",   # Robotics
    "cs.NE",   # Neural and Evolutionary Computing
]


class ArxivSpider(BaseTechSpider):
    name = "arxiv"
    allowed_domains = ["export.arxiv.org"]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def __init__(self, max_results=50, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_results = int(max_results)

    def start_requests(self):
        cat_query = " OR ".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
        params = {
            "search_query": cat_query,
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"http://export.arxiv.org/api/query?{urlencode(params)}"
        yield scrapy.Request(url, callback=self.parse, errback=self.errback_handler)

    def parse(self, response):
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        entries = response.xpath("//atom:entry", namespaces=ns)
        logger.info("ArXiv: found %d entries", len(entries))

        for entry in entries:
            title = entry.xpath("atom:title/text()", namespaces=ns).get("").strip()
            summary = entry.xpath("atom:summary/text()", namespaces=ns).get("").strip()
            paper_id = entry.xpath("atom:id/text()", namespaces=ns).get("")
            published = entry.xpath("atom:published/text()", namespaces=ns).get("")
            authors = entry.xpath("atom:author/atom:name/text()", namespaces=ns).getall()
            categories = entry.xpath("arxiv:primary_category/@term", namespaces=ns).getall()
            pdf_link = entry.xpath('atom:link[@title="pdf"]/@href', namespaces=ns).get("")

            yield self.make_article(
                title=title,
                content=summary,
                summary=summary,
                url=paper_id,
                published_at=published,
                source="arxiv",
                category="academic",
                language="en",
                authors=authors,
                tags=categories,
                extra={"pdf_url": pdf_link, "arxiv_id": paper_id.split("/abs/")[-1] if "/abs/" in paper_id else paper_id},
            )
