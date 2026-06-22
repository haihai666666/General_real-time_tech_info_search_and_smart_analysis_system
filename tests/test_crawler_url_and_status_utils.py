import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRAPY_PROJECT = PROJECT_ROOT / "crawler" / "scrapy_project"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRAPY_PROJECT))


class CrawlerUrlAndStatusUtilsTests(unittest.TestCase):
    def test_geekpark_article_url_accepts_news_paths_only(self):
        from tech_spider.spiders.url_utils import is_geekpark_article_url

        self.assertTrue(is_geekpark_article_url("https://www.geekpark.net/news/364397"))
        self.assertFalse(is_geekpark_article_url("https://www.geekpark.net/tags/RSS"))
        self.assertFalse(is_geekpark_article_url("https://www.geekpark.net/"))

    def test_ithome_article_url_rejects_channel_pages(self):
        from tech_spider.spiders.url_utils import is_ithome_article_url

        self.assertTrue(is_ithome_article_url("https://www.ithome.com/0/957/505.htm"))
        self.assertFalse(is_ithome_article_url("https://www.ithome.com/rss/"))
        self.assertFalse(is_ithome_article_url("https://www.ithome.com/pc/"))
        self.assertFalse(is_ithome_article_url("https://quan.ithome.com"))

    def test_extracts_scrapy_finish_counts(self):
        from crawler.crawl_status_utils import extract_spider_counts

        stderr = "2026 [tech_spider.pipelines] INFO: Spider ithome finished: 40 total, 3 new"

        self.assertEqual(extract_spider_counts("", stderr), {"total_items": 40, "new_items": 3})


if __name__ == "__main__":
    unittest.main()
