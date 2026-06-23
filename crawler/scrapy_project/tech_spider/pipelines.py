import json
import logging
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(
    os.getenv(
        "CRAWLER_DATA_DIR",
        str(Path(__file__).resolve().parent.parent.parent.parent / "data"),
    )
)


class CleaningPipeline:
    """数据清洗管道：去除HTML残余、广告文本、多余空白"""

    AD_PATTERNS = [
        r"subscribe\s+to\s+our\s+newsletter",
        r"sign\s+up\s+for\s+free",
        r"advertisement",
        r"sponsored\s+content",
        r"cookie\s+policy",
    ]

    def process_item(self, item, spider):
        if item.get("content"):
            text = item["content"]
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"&[a-zA-Z]+;", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            for pattern in self.AD_PATTERNS:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            item["content"] = text.strip()

        if item.get("title"):
            item["title"] = re.sub(r"\s+", " ", item["title"]).strip()

        if not item.get("crawled_at"):
            item["crawled_at"] = datetime.now(timezone.utc).isoformat()

        if not item.get("language"):
            item["language"] = "en"

        return item


class DuplicateFilterPipeline:
    """基于URL去重"""

    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item, spider):
        url = item.get("url", "")
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self.seen_urls:
            from scrapy.exceptions import DropItem

            raise DropItem(f"Duplicate article: {url}")
        self.seen_urls.add(url_hash)
        return item


class JsonFilePipeline:
    """将爬取结果写入本地 JSON 文件（按来源分目录，无外部数据库依赖）"""

    def __init__(self):
        self.articles_dir = DATA_DIR / "articles"
        self.logs_dir = DATA_DIR / "logs"
        self.stats = {}

    def open_spider(self, spider):
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.stats[spider.name] = {"total": 0, "new": 0, "failed": 0}
        self._existing_urls = set()

        index_file = self.articles_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
                self._existing_urls = {a["url"] for a in index if "url" in a}
            except (json.JSONDecodeError, KeyError):
                self._existing_urls = set()

    def close_spider(self, spider):
        stat = self.stats.get(spider.name, {})
        status = getattr(spider, "crawl_status", None)
        if status is None:
            status = (
                "failed"
                if stat.get("total", 0) == 0 and getattr(spider, "error_count", 0)
                else "success"
            )
        log_entry = {
            "spider": spider.name,
            "status": status,
            "total_items": stat.get("total", 0),
            "new_items": stat.get("new", 0),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        log_file = self.logs_dir / "crawl_logs.json"
        logs = []
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
        logs.append(log_entry)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        logger.info(
            "Spider %s finished: %d total, %d new",
            spider.name,
            stat.get("total", 0),
            stat.get("new", 0),
        )

    def process_item(self, item, spider):
        stat = self.stats.setdefault(spider.name, {"total": 0, "new": 0, "failed": 0})
        stat["total"] += 1

        doc = dict(item)
        url = doc.get("url", "")

        if url in self._existing_urls:
            logger.debug("Article already exists: %s", url)
            return item

        doc["id"] = hashlib.md5(url.encode()).hexdigest()
        doc["status"] = "raw"

        if doc.get("tags") and not isinstance(doc["tags"], list):
            doc["tags"] = [doc["tags"]]
        if doc.get("authors") and not isinstance(doc["authors"], list):
            doc["authors"] = [doc["authors"]]

        source_dir = self.articles_dir / doc.get("source", "unknown")
        source_dir.mkdir(parents=True, exist_ok=True)
        article_file = source_dir / f"{doc['id']}.json"
        with open(article_file, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        index_file = self.articles_dir / "index.json"
        index = []
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except json.JSONDecodeError:
                index = []

        index_entry = {
            "id": doc["id"],
            "title": doc.get("title", ""),
            "source": doc.get("source", ""),
            "url": url,
            "published_at": doc.get("published_at", ""),
            "crawled_at": doc.get("crawled_at", ""),
            "category": doc.get("category", ""),
            "status": "raw",
        }
        index.append(index_entry)
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        self._existing_urls.add(url)
        stat["new"] += 1
        return item


class MongoDBPipeline:
    """写入MongoDB（需要 pymongo）"""

    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.db = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DATABASE"),
        )

    def open_spider(self, spider):
        import pymongo as _pymongo

        self.client = _pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.db.tech_articles.create_index([("url", _pymongo.ASCENDING)], unique=True)
        self.db.tech_articles.create_index([("published_at", _pymongo.DESCENDING)])
        self.db.tech_articles.create_index([("source", _pymongo.ASCENDING)])
        self.db.tech_articles.create_index([("status", _pymongo.ASCENDING)])

    def close_spider(self, spider):
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        import pymongo as _pymongo

        doc = dict(item)
        doc["status"] = "raw"
        try:
            self.db.tech_articles.update_one(
                {"url": doc["url"]},
                {"$setOnInsert": doc},
                upsert=True,
            )
        except _pymongo.errors.DuplicateKeyError:
            logger.debug("Article already exists: %s", doc.get("url"))
        except Exception as e:
            logger.error("MongoDB write error: %s", e)
        return item


class MySQLLogPipeline:
    """记录爬取日志到MySQL（需要 pymysql）"""

    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.conn = None
        self.stats = {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get("MYSQL_HOST"),
            port=crawler.settings.get("MYSQL_PORT"),
            user=crawler.settings.get("MYSQL_USER"),
            password=crawler.settings.get("MYSQL_PASSWORD"),
            database=crawler.settings.get("MYSQL_DATABASE"),
        )

    def open_spider(self, spider):
        import pymysql as _pymysql

        self.conn = _pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
        )
        self.stats[spider.name] = {"total": 0, "new": 0, "failed": 0}

    def close_spider(self, spider):
        stat = self.stats.get(spider.name, {})
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO crawl_logs (site_name, status, total_items, new_items, finished_at)
                       VALUES (%s, 'success', %s, %s, NOW())""",
                    (spider.name, stat.get("total", 0), stat.get("new", 0)),
                )
            self.conn.commit()
        except Exception as e:
            logger.error("MySQL log write error: %s", e)
        finally:
            if self.conn:
                self.conn.close()

    def process_item(self, item, spider):
        stat = self.stats.setdefault(spider.name, {"total": 0, "new": 0, "failed": 0})
        stat["total"] += 1
        stat["new"] += 1
        return item
