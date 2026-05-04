"""GitHub Trending 爬虫 - 抓取热门开源项目动态"""

import logging
from datetime import datetime, timezone

import scrapy

from tech_spider.spiders.base_spider import BaseTechSpider

logger = logging.getLogger(__name__)


class GithubTrendingSpider(BaseTechSpider):
    name = "github_trending"
    allowed_domains = ["github.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
    }

    LANGUAGES = ["python", "javascript", "typescript", "rust", "go", "java", ""]
    TIME_RANGES = ["daily"]

    def start_requests(self):
        for lang in self.LANGUAGES:
            for since in self.TIME_RANGES:
                url = f"https://github.com/trending/{lang}?since={since}"
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    errback=self.errback_handler,
                    meta={"language": lang or "all", "since": since},
                )

    def parse(self, response):
        lang = response.meta["language"]
        rows = response.css("article.Box-row")
        logger.info("GitHub Trending (%s): found %d repos", lang, len(rows))

        for row in rows:
            repo_link = row.css("h2 a::attr(href)").get("")
            repo_name = repo_link.strip("/") if repo_link else ""
            description = row.css("p.col-9::text").get("").strip()
            prog_lang = row.css("span[itemprop='programmingLanguage']::text").get("").strip()
            stars_today = row.css("span.d-inline-block.float-sm-right::text").get("").strip()
            total_stars = row.css("a.Link--muted:first-of-type::text").get("").strip().replace(",", "")

            if not repo_name:
                continue

            full_url = f"https://github.com{repo_link}"
            content = f"Repository: {repo_name}\n"
            if description:
                content += f"Description: {description}\n"
            if prog_lang:
                content += f"Language: {prog_lang}\n"
            if total_stars:
                content += f"Total Stars: {total_stars}\n"
            if stars_today:
                content += f"Stars Today: {stars_today.strip()}\n"

            tags = [t for t in [prog_lang.lower(), lang] if t and t != "all"]
            tags.append("open-source")

            yield self.make_article(
                title=f"[Trending] {repo_name}",
                content=content,
                summary=description,
                url=full_url,
                published_at=datetime.now(timezone.utc).isoformat(),
                source="github",
                category="open-source",
                tags=tags,
                extra={"stars": total_stars, "stars_today": stars_today.strip(), "prog_language": prog_lang},
            )
