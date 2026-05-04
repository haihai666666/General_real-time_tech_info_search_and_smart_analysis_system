import os

BOT_NAME = "tech_spider"
SPIDER_MODULES = ["tech_spider.spiders"]
NEWSPIDER_MODULE = "tech_spider.spiders"

ROBOTSTXT_OBEY = False

CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}

DOWNLOADER_MIDDLEWARES = {
    "tech_spider.middlewares.RandomUserAgentMiddleware": 400,
    "tech_spider.middlewares.RetryWithLoggingMiddleware": 550,
}

ITEM_PIPELINES = {
    "tech_spider.pipelines.CleaningPipeline": 100,
    "tech_spider.pipelines.DuplicateFilterPipeline": 200,
    "tech_spider.pipelines.JsonFilePipeline": 300,
}

RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
HTTPERROR_ALLOWED_CODES = [403, 404]

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/techinfo")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "techinfo")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "techinfo")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "techinfo_pass_2026")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "techinfo")

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
