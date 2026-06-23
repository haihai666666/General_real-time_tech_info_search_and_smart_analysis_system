"""Celery 爬虫任务定义"""

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from crawler.tasks.celery_app import app

logger = logging.getLogger(__name__)

SCRAPY_PROJECT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scrapy_project"
)


@app.task(bind=True, max_retries=2, default_retry_delay=300)
def run_spider(self, spider_name: str, extra_args: dict | None = None):
    """运行指定的 Scrapy 爬虫"""
    logger.info("Starting spider: %s (task_id=%s)", spider_name, self.request.id)
    start_time = datetime.now(timezone.utc)

    cmd = [sys.executable, "-m", "scrapy", "crawl", spider_name]
    if extra_args:
        for k, v in extra_args.items():
            cmd.extend(["-a", f"{k}={v}"])

    try:
        result = subprocess.run(
            cmd,
            cwd=SCRAPY_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        if result.returncode == 0:
            logger.info("Spider %s completed in %.1fs", spider_name, elapsed)
            return {
                "spider": spider_name,
                "status": "success",
                "duration": elapsed,
                "stdout_tail": result.stdout[-500:] if result.stdout else "",
            }
        else:
            logger.error(
                "Spider %s failed (code=%d): %s",
                spider_name,
                result.returncode,
                result.stderr[-500:],
            )
            raise Exception(
                f"Spider {spider_name} exited with code {result.returncode}"
            )

    except subprocess.TimeoutExpired:
        logger.error("Spider %s timed out after 30min", spider_name)
        raise self.retry(exc=Exception(f"Timeout: {spider_name}"))
    except Exception as exc:
        logger.error("Spider %s error: %s", spider_name, exc)
        raise self.retry(exc=exc)


@app.task
def run_all_spiders():
    """按顺序触发所有爬虫"""
    spiders = ["arxiv", "github_trending", "mit_news", "techcrunch", "ieee_spectrum"]
    results = []
    for spider_name in spiders:
        task = run_spider.delay(spider_name)
        results.append({"spider": spider_name, "task_id": task.id})
    return results
