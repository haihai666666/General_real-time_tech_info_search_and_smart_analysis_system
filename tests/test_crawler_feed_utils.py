import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRAPY_PROJECT = PROJECT_ROOT / "crawler" / "scrapy_project"
sys.path.insert(0, str(SCRAPY_PROJECT))


class FeedUtilsTests(unittest.TestCase):
    def test_extracts_v2ex_atom_entries(self):
        from tech_spider.spiders.feed_utils import extract_feed_entries

        xml = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>V2EX topic</title>
            <link rel="alternate" type="text/html" href="https://www.v2ex.com/t/1#reply2" />
            <published>2026-05-31T05:38:08Z</published>
            <author><name>alice</name></author>
            <content type="html"><![CDATA[hello <b>world</b>]]></content>
          </entry>
        </feed>
        """

        entries = extract_feed_entries(xml)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "V2EX topic")
        self.assertEqual(entries[0]["link"], "https://www.v2ex.com/t/1#reply2")
        self.assertEqual(entries[0]["content"], "hello <b>world</b>")
        self.assertEqual(entries[0]["published_at"], "2026-05-31T05:38:08Z")
        self.assertEqual(entries[0]["authors"], ["alice"])

    def test_extracts_huxiu_rss_items(self):
        from tech_spider.spiders.feed_utils import extract_feed_entries

        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title><![CDATA[虎嗅标题]]></title>
              <link>https://www.huxiu.com/article/1.html?f=rss</link>
              <description><![CDATA[<p>虎嗅正文</p>]]></description>
              <pubDate>Sun, 31 May 2026 12:00:00 GMT</pubDate>
              <category>科技</category>
            </item>
          </channel>
        </rss>
        """

        entries = extract_feed_entries(xml)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "虎嗅标题")
        self.assertEqual(entries[0]["link"], "https://www.huxiu.com/article/1.html?f=rss")
        self.assertEqual(entries[0]["content"], "<p>虎嗅正文</p>")
        self.assertEqual(entries[0]["published_at"], "Sun, 31 May 2026 12:00:00 GMT")
        self.assertEqual(entries[0]["tags"], ["科技"])


if __name__ == "__main__":
    unittest.main()
