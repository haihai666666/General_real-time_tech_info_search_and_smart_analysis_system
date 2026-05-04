"""
智能分析 API 路由

提供以下功能：
- 单篇文章摘要
- 批量趋势分析
- 基于上下文的问答（支持流式）
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from algorithm.analysis import (
    analyze_trends,
    qa_stream,
    qa_with_context,
    summarize_article,
)
from crawler.api import _load_article, _load_index

logger = logging.getLogger("algorithm.api")

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class SummarizeRequest(BaseModel):
    article_id: str


class TrendRequest(BaseModel):
    source: Optional[str] = None
    limit: int = 20


class Message(BaseModel):
    role: str
    content: str


class QARequest(BaseModel):
    question: str
    source: Optional[str] = None
    stream: bool = False
    history: list[Message] = []


@router.post("/summarize")
async def api_summarize(req: SummarizeRequest):
    """为指定文章生成摘要"""
    index = _load_index()
    entry = next((a for a in index if a["id"] == req.article_id), None)
    if not entry:
        raise HTTPException(404, "Article not found")

    article = _load_article(req.article_id, entry.get("source", "unknown"))
    if not article:
        raise HTTPException(404, "Article file not found")

    try:
        summary = await summarize_article(article)
        return {"article_id": req.article_id, "title": article.get("title", ""), "summary": summary}
    except ValueError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error("Summarize failed: %s", e)
        raise HTTPException(500, f"Analysis failed: {e}")


@router.post("/trends")
async def api_trends(req: TrendRequest):
    """分析技术趋势"""
    index = _load_index()
    if req.source:
        index = [a for a in index if a.get("source") == req.source]

    index.sort(key=lambda x: x.get("crawled_at", ""), reverse=True)
    entries = index[:req.limit]

    articles = []
    for entry in entries:
        article = _load_article(entry["id"], entry.get("source", "unknown"))
        if article:
            articles.append(article)

    if not articles:
        return {"analysis": "No articles available for analysis.", "article_count": 0}

    try:
        analysis = await analyze_trends(articles)
        return {"analysis": analysis, "article_count": len(articles)}
    except ValueError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error("Trend analysis failed: %s", e)
        raise HTTPException(500, f"Analysis failed: {e}")


@router.post("/qa")
async def api_qa(req: QARequest):
    """基于文章上下文的问答"""
    index = _load_index()
    if req.source:
        index = [a for a in index if a.get("source") == req.source]

    index.sort(key=lambda x: x.get("crawled_at", ""), reverse=True)

    articles = []
    for entry in index[:10]:
        article = _load_article(entry["id"], entry.get("source", "unknown"))
        if article:
            articles.append(article)

    history = [{"role": m.role, "content": m.content} for m in req.history] if req.history else None

    try:
        if req.stream:
            async def stream_generator():
                gen = await qa_stream(req.question, articles, history)
                async for chunk in gen:
                    yield json.dumps({"response": chunk}, ensure_ascii=False) + "\n"

            return StreamingResponse(
                stream_generator(),
                media_type="application/x-ndjson",
            )
        else:
            answer = await qa_with_context(req.question, articles, history)
            return {"question": req.question, "answer": answer, "sources_count": len(articles)}
    except ValueError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.error("QA failed: %s", e)
        raise HTTPException(500, f"QA failed: {e}")
