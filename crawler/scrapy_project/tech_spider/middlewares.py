import logging
from fake_useragent import UserAgent
from scrapy.downloadermiddlewares.retry import RetryMiddleware

logger = logging.getLogger(__name__)


class RandomUserAgentMiddleware:
    """随机User-Agent中间件"""

    def __init__(self):
        try:
            self.ua = UserAgent(
                fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
        except Exception:
            self.ua = None
        self.fallback = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def process_request(self, request, spider):
        if self.ua:
            try:
                request.headers["User-Agent"] = self.ua.random
                return
            except Exception:
                pass
        request.headers["User-Agent"] = self.fallback


class RetryWithLoggingMiddleware(RetryMiddleware):
    """带日志的重试中间件"""

    def _retry(self, request, reason, spider):
        logger.warning(
            "Retrying %s (reason: %s, spider: %s)",
            request.url,
            reason,
            spider.name,
        )
        return super()._retry(request, reason, spider)
