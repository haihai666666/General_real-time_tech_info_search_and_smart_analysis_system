"""
爬虫管理与文章查询 API 路由 —— JSON 文件后端（无外部数据库依赖）
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv(
    "CRAWLER_DATA_DIR",
    str(Path(__file__).resolve().parent.parent.parent.parent / "data"),
))
ARTICLES_DIR = DATA_DIR / "articles"
LOGS_DIR = DATA_DIR / "logs"
SCRAPY_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "crawler" / "scrapy_project"


# ───── Pydantic Models ─────

class ArticleResponse(BaseModel):
    id: str = ""
    title: str = ""
    content: str = ""
    summary: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""
    crawled_at: str = ""
    category: str = ""
    tags: list = []
    authors: list = []
    status: str = "raw"
    extra: dict = {}


class ArticleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    articles: list[dict]


class CrawlStatsResponse(BaseModel):
    total_articles: int = 0
    today_new: int = 0
    sources: dict = {}
    categories: dict = {}
    latest_crawl: Optional[str] = None


class TriggerCrawlRequest(BaseModel):
    spider_name: str
    max_results: int = Field(default=20, ge=1, le=200)


class TriggerCrawlResponse(BaseModel):
    spider_name: str
    status: str
    message: str


class IngestRequest(BaseModel):
    source: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)


class IngestResponse(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    message: str = ""


# ───── Helper functions ─────

def _load_index() -> list[dict]:
    index_file = ARTICLES_DIR / "index.json"
    if not index_file.exists():
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _load_article(article_id: str, source: str = None) -> Optional[dict]:
    if source:
        dirs = [ARTICLES_DIR / source]
    else:
        dirs = [d for d in ARTICLES_DIR.iterdir() if d.is_dir()]

    for d in dirs:
        article_file = d / f"{article_id}.json"
        if article_file.exists():
            with open(article_file, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _load_crawl_logs() -> list[dict]:
    log_file = LOGS_DIR / "crawl_logs.json"
    if not log_file.exists():
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _run_spider_sync(spider_name: str, max_results: int = 20):
    """在后台线程运行 Scrapy 爬虫"""
    cmd = [sys.executable, "-m", "scrapy", "crawl", spider_name]
    if spider_name == "arxiv":
        cmd.extend(["-a", f"max_results={max_results}"])

    logger.info("Running spider: %s (cmd: %s)", spider_name, " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRAPY_PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            logger.info("Spider %s completed successfully", spider_name)
        else:
            logger.error("Spider %s failed: %s", spider_name, result.stderr[-500:] if result.stderr else "unknown")
    except subprocess.TimeoutExpired:
        logger.error("Spider %s timed out", spider_name)
    except Exception as e:
        logger.error("Spider %s error: %s", spider_name, e)


# ───── Router Factory ─────

def create_crawler_routes():
    router = APIRouter(prefix="/api/crawler", tags=["Crawler"])

    @router.get("/articles", response_model=ArticleListResponse)
    async def list_articles(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        source: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """获取科技文章列表，支持多维筛选"""
        index = _load_index()

        filtered = []
        for entry in index:
            if source and entry.get("source") != source:
                continue
            if category and entry.get("category") != category:
                continue
            if status and entry.get("status") != status:
                continue
            if keyword:
                kw = keyword.lower()
                if kw not in entry.get("title", "").lower():
                    continue
            filtered.append(entry)

        filtered.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        articles = []
        for entry in page_items:
            article = _load_article(entry["id"], entry.get("source"))
            if article:
                articles.append(article)
            else:
                articles.append(entry)

        return ArticleListResponse(
            total=total, page=page, page_size=page_size, articles=articles,
        )

    @router.get("/articles/{article_id}", response_model=ArticleResponse)
    async def get_article(article_id: str):
        """获取文章详情"""
        article = _load_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        return ArticleResponse(**article)

    @router.get("/stats", response_model=CrawlStatsResponse)
    async def get_crawl_stats():
        """获取爬取统计数据"""
        index = _load_index()
        total = len(index)

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_new = sum(1 for a in index if a.get("crawled_at", "").startswith(today_str))

        sources = {}
        categories = {}
        for a in index:
            s = a.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1
            c = a.get("category", "general")
            categories[c] = categories.get(c, 0) + 1

        logs = _load_crawl_logs()
        latest_crawl = logs[-1].get("finished_at", "") if logs else None

        return CrawlStatsResponse(
            total_articles=total,
            today_new=today_new,
            sources=sources,
            categories=categories,
            latest_crawl=latest_crawl,
        )

    @router.get("/logs")
    async def get_crawl_logs(limit: int = Query(50, ge=1, le=200)):
        """获取爬虫运行日志"""
        logs = _load_crawl_logs()
        logs.sort(key=lambda x: x.get("finished_at", ""), reverse=True)
        return logs[:limit]

    @router.post("/trigger", response_model=TriggerCrawlResponse)
    async def trigger_crawl(req: TriggerCrawlRequest, background_tasks: BackgroundTasks):
        """手动触发爬虫任务（后台运行）"""
        valid_spiders = ["arxiv", "github_trending", "mit_news", "techcrunch", "ieee_spectrum"]
        if req.spider_name not in valid_spiders:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown spider: {req.spider_name}. Valid: {valid_spiders}",
            )

        background_tasks.add_task(_run_spider_sync, req.spider_name, req.max_results)

        return TriggerCrawlResponse(
            spider_name=req.spider_name,
            status="started",
            message=f"Spider '{req.spider_name}' triggered in background",
        )

    @router.post("/ingest", response_model=IngestResponse)
    async def ingest_articles(req: IngestRequest, background_tasks: BackgroundTasks):
        """将爬取的文章导入 LightRAG 知识图谱"""
        index = _load_index()

        candidates = []
        for entry in index:
            if entry.get("status") != "raw":
                continue
            if req.source and entry.get("source") != req.source:
                continue
            candidates.append(entry)
            if len(candidates) >= req.limit:
                break

        if not candidates:
            return IngestResponse(message="No raw articles to ingest")

        api_url = os.getenv("LIGHTRAG_API_URL", "http://localhost:9622")
        background_tasks.add_task(_run_ingest, candidates, api_url)

        return IngestResponse(
            total=len(candidates),
            message=f"Ingesting {len(candidates)} articles in background",
        )

    @router.get("/sources")
    async def get_available_sources():
        """获取所有可用的数据来源"""
        index = _load_index()
        sources = list(set(a.get("source", "") for a in index if a.get("source")))
        return {"sources": sorted(sources)}

    @router.get("/categories")
    async def get_available_categories():
        """获取所有可用的分类"""
        index = _load_index()
        categories = list(set(a.get("category", "") for a in index if a.get("category")))
        return {"categories": sorted(categories)}

    @router.get("/spiders")
    async def get_available_spiders():
        """获取所有可用的爬虫列表"""
        return {
            "spiders": [
                {"name": "arxiv", "description": "ArXiv CS papers (API-based, most reliable)", "category": "academic"},
                {"name": "github_trending", "description": "GitHub Trending repositories", "category": "open-source"},
                {"name": "mit_news", "description": "MIT News technology articles", "category": "research"},
                {"name": "techcrunch", "description": "TechCrunch RSS feed", "category": "tech_news"},
                {"name": "ieee_spectrum", "description": "IEEE Spectrum articles", "category": "technology"},
            ]
        }

    return router


def _run_ingest(candidates: list[dict], api_url: str):
    """后台执行文章导入"""
    try:
        import requests as req_lib
    except ImportError:
        logger.error("requests library not available for ingest")
        return

    index_file = ARTICLES_DIR / "index.json"

    for entry in candidates:
        article = _load_article(entry["id"], entry.get("source"))
        if not article:
            continue

        parts = []
        title = article.get("title", "").strip()
        if title:
            parts.append(f"Title: {title}")
        source = article.get("source", "")
        published = article.get("published_at", "")
        if source or published:
            meta = []
            if source:
                meta.append(f"Source: {source}")
            if published:
                meta.append(f"Published: {published}")
            parts.append(" | ".join(meta))
        authors = article.get("authors", [])
        if authors:
            parts.append(f"Authors: {', '.join(authors)}")
        content = article.get("content", "").strip()
        if content:
            parts.append(f"\n{content}")
        text = "\n".join(parts)

        if len(text.strip()) < 50:
            continue

        try:
            token = os.getenv("LIGHTRAG_API_TOKEN", "")
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            resp = req_lib.post(
                f"{api_url}/documents/text",
                json={"text": text},
                headers=headers,
                timeout=300,
            )
            if resp.status_code in (200, 201):
                _update_index_status(index_file, entry["id"], "ingested")
                logger.info("Ingested article: %s", title[:60])
            else:
                logger.error("Failed to ingest '%s': HTTP %d", title[:60], resp.status_code)
        except Exception as e:
            logger.error("Ingest error for '%s': %s", title[:60], e)


def _update_index_status(index_file: Path, article_id: str, status: str):
    """更新 index.json 中指定文章的状态"""
    if not index_file.exists():
        return
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            index = json.load(f)
        for entry in index:
            if entry.get("id") == article_id:
                entry["status"] = status
                break
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to update index status: %s", e)
