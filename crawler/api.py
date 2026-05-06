"""
爬虫管理 + 文章查询 API 路由

提供以下功能：
- 触发爬虫任务（指定 spider 名称）
- 查看爬虫运行状态和日志
- 文章列表查询（分页、按来源过滤、搜索）
- 单篇文章详情
- 手动触发数据导入 LightRAG
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

logger = logging.getLogger("crawler.api")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARTICLES_DIR = DATA_DIR / "articles"
LOGS_DIR = DATA_DIR / "logs"
SCRAPY_PROJECT_DIR = Path(__file__).resolve().parent / "scrapy_project"

AVAILABLE_SPIDERS = {
    "arxiv": {"name": "arxiv", "description": "ArXiv CS papers via Atom API", "category": "academic"},
    "github_trending": {"name": "github_trending", "description": "GitHub Trending repositories", "category": "open-source"},
    "techcrunch": {"name": "techcrunch", "description": "TechCrunch tech news via RSS", "category": "tech_news"},
    "mit_news": {"name": "mit_news", "description": "MIT Technology News", "category": "research"},
    "ieee_spectrum": {"name": "ieee_spectrum", "description": "IEEE Spectrum tech articles", "category": "technology"},
    "36kr": {"name": "36kr", "description": "36氪科技资讯", "category": "tech_news_cn"},
    "ifanr": {"name": "ifanr", "description": "爱范儿消费科技", "category": "consumer_tech_cn"},
    "infoq_cn": {"name": "infoq_cn", "description": "InfoQ 中文技术资讯", "category": "software_dev_cn"},
}

_running_tasks: dict[str, dict] = {}

router = APIRouter(prefix="/api/crawler", tags=["crawler"])


# --------------- Models ---------------

class CrawlRequest(BaseModel):
    spider: str
    max_results: int = 20


class IngestRequest(BaseModel):
    source: Optional[str] = None
    limit: Optional[int] = None


class ArticleResponse(BaseModel):
    id: str
    title: str
    source: str
    url: str
    published_at: str
    crawled_at: str
    category: str
    status: str
    summary: Optional[str] = None
    tags: list[str] = []
    authors: list[str] = []


class ArticlesPageResponse(BaseModel):
    articles: list[ArticleResponse]
    total: int
    page: int
    page_size: int


class SpiderInfo(BaseModel):
    name: str
    description: str
    category: str
    is_running: bool = False


class CrawlStatusResponse(BaseModel):
    spider: str
    status: str  # running / completed / failed
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    items_count: int = 0
    error: Optional[str] = None


class CrawlLogEntry(BaseModel):
    spider: str
    status: str
    total_items: int
    new_items: int
    finished_at: str


# --------------- Helpers ---------------

def _load_index() -> list[dict]:
    index_file = ARTICLES_DIR / "index.json"
    if not index_file.exists():
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _load_article(article_id: str, source: str) -> Optional[dict]:
    article_file = ARTICLES_DIR / source / f"{article_id}.json"
    if not article_file.exists():
        return None
    try:
        with open(article_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _run_spider_process(spider_name: str, max_results: int, task_id: str):
    """在子进程中运行 Scrapy 爬虫"""
    _running_tasks[task_id]["status"] = "running"
    try:
        # Use the same Python interpreter as the running API server
        python_exe = sys.executable or "python"
        cmd = [
            python_exe, "-m", "scrapy", "crawl", spider_name,
            "-a", f"max_results={max_results}",
            "-s", "LOG_LEVEL=INFO",
        ]
        logger.info("Starting spider process: %s | cwd=%s", " ".join(cmd), SCRAPY_PROJECT_DIR)

        result = subprocess.run(
            cmd,
            cwd=str(SCRAPY_PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )

        _running_tasks[task_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        stdout_tail = (result.stdout or "")[-2000:]
        stderr_tail = (result.stderr or "")[-2000:]

        if result.returncode == 0:
            _running_tasks[task_id]["status"] = "completed"
            _running_tasks[task_id]["log_tail"] = stdout_tail or "Spider finished with no stdout"
            logger.info("Spider completed: %s", spider_name)
        else:
            _running_tasks[task_id]["status"] = "failed"
            _running_tasks[task_id]["error"] = (
                f"Spider exit code {result.returncode}. "
                f"STDERR: {stderr_tail or '<empty>'} | STDOUT: {stdout_tail or '<empty>'}"
            )
            logger.error("Spider failed: %s | rc=%s | stderr=%s", spider_name, result.returncode, stderr_tail)
    except subprocess.TimeoutExpired:
        _running_tasks[task_id]["status"] = "failed"
        _running_tasks[task_id]["error"] = "Spider timed out after 300s"
        _running_tasks[task_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.error("Spider timed out: %s", spider_name)
    except Exception as e:
        _running_tasks[task_id]["status"] = "failed"
        _running_tasks[task_id]["error"] = str(e)
        _running_tasks[task_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.exception("Spider crashed: %s", spider_name)


# --------------- Endpoints ---------------

@router.get("/spiders", response_model=list[SpiderInfo])
async def list_spiders():
    """列出所有可用的爬虫"""
    result = []
    for key, info in AVAILABLE_SPIDERS.items():
        is_running = any(
            t["spider"] == key and t["status"] == "running"
            for t in _running_tasks.values()
        )
        result.append(SpiderInfo(**info, is_running=is_running))
    return result


@router.post("/crawl", response_model=CrawlStatusResponse)
async def trigger_crawl(req: CrawlRequest):
    """触发一个爬虫任务"""
    if req.spider not in AVAILABLE_SPIDERS:
        raise HTTPException(400, f"Unknown spider: {req.spider}")

    running = [
        t for t in _running_tasks.values()
        if t["spider"] == req.spider and t["status"] == "running"
    ]
    if running:
        raise HTTPException(409, f"Spider '{req.spider}' is already running")

    task_id = f"{req.spider}_{int(time.time())}"
    _running_tasks[task_id] = {
        "spider": req.spider,
        "status": "starting",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "items_count": 0,
        "error": None,
    }

    thread = threading.Thread(
        target=_run_spider_process,
        args=(req.spider, req.max_results, task_id),
        daemon=True,
    )
    thread.start()

    return CrawlStatusResponse(
        spider=req.spider,
        status="starting",
        started_at=_running_tasks[task_id]["started_at"],
    )


@router.get("/status")
async def crawl_status():
    """获取所有爬虫任务的状态"""
    return {
        "tasks": {
            tid: {
                "spider": t["spider"],
                "status": t["status"],
                "started_at": t.get("started_at"),
                "finished_at": t.get("finished_at"),
                "error": t.get("error"),
            }
            for tid, t in _running_tasks.items()
        }
    }


@router.get("/logs", response_model=list[CrawlLogEntry])
async def crawl_logs(limit: int = Query(20, ge=1, le=100)):
    """获取爬虫日志记录"""
    log_file = LOGS_DIR / "crawl_logs.json"
    if not log_file.exists():
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
        logs.sort(key=lambda x: x.get("finished_at", ""), reverse=True)
        return [CrawlLogEntry(**entry) for entry in logs[:limit]]
    except (json.JSONDecodeError, IOError):
        return []


@router.get("/articles", response_model=ArticlesPageResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """分页查询文章列表"""
    index = _load_index()

    if source:
        index = [a for a in index if a.get("source") == source]
    if category:
        index = [a for a in index if a.get("category") == category]
    if status:
        index = [a for a in index if a.get("status") == status]
    if search:
        search_lower = search.lower()
        index = [a for a in index if search_lower in a.get("title", "").lower()]

    index.sort(key=lambda x: x.get("crawled_at", ""), reverse=True)
    total = len(index)

    start = (page - 1) * page_size
    page_items = index[start:start + page_size]

    articles = []
    for entry in page_items:
        full = _load_article(entry["id"], entry.get("source", "unknown"))
        articles.append(ArticleResponse(
            id=entry["id"],
            title=entry.get("title", ""),
            source=entry.get("source", ""),
            url=entry.get("url", ""),
            published_at=entry.get("published_at", ""),
            crawled_at=entry.get("crawled_at", ""),
            category=entry.get("category", ""),
            status=entry.get("status", "raw"),
            summary=(full.get("summary", "") if full else "")[:300],
            tags=full.get("tags", []) if full else [],
            authors=full.get("authors", []) if full else [],
        ))

    return ArticlesPageResponse(
        articles=articles, total=total, page=page, page_size=page_size
    )


@router.get("/articles/{article_id}")
async def get_article(article_id: str):
    """获取单篇文章详情"""
    index = _load_index()
    entry = next((a for a in index if a["id"] == article_id), None)
    if not entry:
        raise HTTPException(404, "Article not found")

    article = _load_article(article_id, entry.get("source", "unknown"))
    if not article:
        raise HTTPException(404, "Article file not found")

    return article


@router.get("/stats")
async def crawl_stats():
    """获取爬取统计信息"""
    index = _load_index()
    sources: dict[str, int] = {}
    statuses: dict[str, int] = {}
    categories: dict[str, int] = {}

    for entry in index:
        src = entry.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        st = entry.get("status", "unknown")
        statuses[st] = statuses.get(st, 0) + 1
        cat = entry.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_articles": len(index),
        "by_source": sources,
        "by_status": statuses,
        "by_category": categories,
    }


@router.post("/ingest")
async def trigger_ingest(req: IngestRequest):
    """触发数据导入 LightRAG（已废弃，使用 /import 代替）"""
    from crawler.ingest import load_articles, format_article_for_rag

    articles = load_articles(source=req.source, limit=req.limit)
    if not articles:
        return {"status": "empty", "message": "No articles to ingest"}

    texts = []
    for article in articles:
        text = format_article_for_rag(article)
        if len(text.strip()) >= 50:
            texts.append({"id": article.get("id", ""), "text": text, "title": article.get("title", "")})

    return {
        "status": "ready",
        "total": len(texts),
        "articles": [{"id": t["id"], "title": t["title"]} for t in texts],
    }


@router.post("/import/batch")
async def import_batch_articles(article_ids: list[str] = Body(...)):
    """批量导入文章到 LightRAG"""
    results = []
    for article_id in article_ids:
        result = await import_single_article(article_id)
        results.append(result)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    
    return {
        "status": "completed",
        "total": len(article_ids),
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "results": results
    }


@router.post("/import/{article_id}")
async def import_single_article(article_id: str):
    """导入单篇文章到 LightRAG"""
    import requests
    from crawler.ingest import format_article_for_rag
    
    # Load article
    index = _load_index()
    entry = next((a for a in index if a["id"] == article_id), None)
    if not entry:
        raise HTTPException(404, "Article not found")
    
    article = _load_article(article_id, entry.get("source", "unknown"))
    if not article:
        raise HTTPException(404, "Article file not found")
    
    # Check if already imported
    if entry.get("status") == "ingested":
        return {"status": "skipped", "message": "Article already imported", "article_id": article_id}
    
    # Format and import
    text = format_article_for_rag(article)
    if len(text.strip()) < 50:
        return {"status": "skipped", "message": "Article content too short", "article_id": article_id}
    
    try:
        # Call LightRAG API
        api_url = os.getenv("LIGHTRAG_API_URL", "http://localhost:9622")
        token = os.getenv("LIGHTRAG_API_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        resp = requests.post(
            f"{api_url}/documents/text",
            json={"text": text},
            headers=headers,
            timeout=300,
        )
        
        if resp.status_code in (200, 201):
            _update_article_status(article_id, "ingested")
            return {
                "status": "success",
                "message": "Article imported successfully",
                "article_id": article_id,
                "title": article.get("title", "")[:100]
            }
        else:
            return {
                "status": "failed",
                "message": f"LightRAG API error: {resp.status_code}",
                "article_id": article_id
            }
    except Exception as e:
        logger.error(f"Import failed for {article_id}: {e}")
        return {"status": "failed", "message": str(e), "article_id": article_id}


def _update_article_status(article_id: str, status: str):
    """更新文章状态"""
    index_file = ARTICLES_DIR / "index.json"
    if not index_file.exists():
        return
    
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            index = json.load(f)
        
        for entry in index:
            if entry["id"] == article_id:
                entry["status"] = status
                break
        
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to update article status: {e}")
