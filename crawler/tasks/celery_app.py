"""Celery 应用配置"""

import os

from celery import Celery
from celery.schedules import crontab

redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

app = Celery("techinfo_crawler", broker=redis_url, backend=redis_url)

app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

app.conf.beat_schedule = {
    "crawl-arxiv-daily": {
        "task": "crawler.tasks.crawl_tasks.run_spider",
        "schedule": crontab(hour=3, minute=0),
        "args": ("arxiv",),
    },
    "crawl-github-trending-daily": {
        "task": "crawler.tasks.crawl_tasks.run_spider",
        "schedule": crontab(hour=4, minute=0),
        "args": ("github_trending",),
    },
    "crawl-mit-news-daily": {
        "task": "crawler.tasks.crawl_tasks.run_spider",
        "schedule": crontab(hour=5, minute=0),
        "args": ("mit_news",),
    },
    "crawl-techcrunch-daily": {
        "task": "crawler.tasks.crawl_tasks.run_spider",
        "schedule": crontab(hour=6, minute=0),
        "args": ("techcrunch",),
    },
    "crawl-ieee-daily": {
        "task": "crawler.tasks.crawl_tasks.run_spider",
        "schedule": crontab(hour=7, minute=0),
        "args": ("ieee_spectrum",),
    },
}

app.autodiscover_tasks(["crawler.tasks"])
