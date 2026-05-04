"""
智能分析模块 — 调用 Qwen 大语言模型进行科技信息分析

功能：
- 单篇文章摘要生成
- 批量文章趋势分析
- 自由问答（基于已采集文章上下文）
"""

import json
import logging
import os
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger("algorithm.analysis")

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
QWEN_TIMEOUT = int(os.getenv("QWEN_TIMEOUT", "120"))


async def _call_qwen(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    stream: bool = False,
) -> str | AsyncIterator[str]:
    """调用 Qwen API（OpenAI 兼容格式）"""
    if not QWEN_API_KEY:
        raise ValueError("QWEN_API_KEY not configured. Set it in .env or environment.")

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": QWEN_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if stream:
        return _stream_qwen(headers, payload)

    async with httpx.AsyncClient(timeout=QWEN_TIMEOUT) as client:
        resp = await client.post(
            f"{QWEN_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _stream_qwen(headers: dict, payload: dict) -> AsyncIterator[str]:
    """流式调用 Qwen API"""
    async with httpx.AsyncClient(timeout=QWEN_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{QWEN_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def summarize_article(article: dict) -> str:
    """为单篇文章生成中文摘要"""
    title = article.get("title", "")
    content = article.get("content", "")[:4000]
    source = article.get("source", "")
    tags = ", ".join(article.get("tags", []))

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位资深的科技分析师。请根据以下科技文章内容，生成一份简洁的中文摘要。"
                "摘要应包含：1) 核心主题；2) 关键技术要点；3) 潜在影响。"
                "控制在200字以内。"
            ),
        },
        {
            "role": "user",
            "content": f"标题：{title}\n来源：{source}\n标签：{tags}\n\n内容：\n{content}",
        },
    ]
    return await _call_qwen(messages, temperature=0.3, max_tokens=500)


async def analyze_trends(articles: list[dict]) -> str:
    """分析一批文章的技术趋势"""
    article_summaries = []
    for i, article in enumerate(articles[:20]):
        title = article.get("title", "")
        source = article.get("source", "")
        tags = ", ".join(article.get("tags", []))
        published = article.get("published_at", "")
        summary = article.get("summary", article.get("content", ""))[:200]
        article_summaries.append(
            f"{i+1}. [{source}] {title}\n   标签: {tags}\n   时间: {published}\n   摘要: {summary}"
        )

    articles_text = "\n\n".join(article_summaries)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位资深的科技趋势分析师。根据以下近期科技文章列表，"
                "分析当前技术发展趋势。请从以下角度进行分析：\n"
                "1. 热门研究方向：哪些技术领域最活跃？\n"
                "2. 新兴技术：有哪些值得关注的新兴技术？\n"
                "3. 行业动态：有哪些重要的产业趋势？\n"
                "4. 预测与建议：基于这些信息，你有什么预测？\n"
                "请使用中文回答，条理清晰。"
            ),
        },
        {
            "role": "user",
            "content": f"以下是最近采集的 {len(articles)} 篇科技文章：\n\n{articles_text}",
        },
    ]
    return await _call_qwen(messages, temperature=0.7, max_tokens=3000)


async def qa_with_context(
    question: str,
    articles: list[dict],
    history: Optional[list[dict]] = None,
) -> str:
    """基于文章上下文的问答"""
    context_parts = []
    for article in articles[:10]:
        title = article.get("title", "")
        content = article.get("content", "")[:500]
        source = article.get("source", "")
        context_parts.append(f"[{source}] {title}\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位知识渊博的科技信息助手。"
                "基于以下参考资料回答用户的问题。"
                "如果参考资料中没有相关信息，请基于你的知识回答，但要说明。"
                "使用中文回答。"
            ),
        },
    ]

    if history:
        messages.extend(history[-6:])

    messages.append({
        "role": "user",
        "content": f"参考资料：\n{context_text}\n\n问题：{question}",
    })

    return await _call_qwen(messages, temperature=0.5, max_tokens=2000)


async def qa_stream(
    question: str,
    articles: list[dict],
    history: Optional[list[dict]] = None,
) -> AsyncIterator[str]:
    """流式问答"""
    context_parts = []
    for article in articles[:10]:
        title = article.get("title", "")
        content = article.get("content", "")[:500]
        source = article.get("source", "")
        context_parts.append(f"[{source}] {title}\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位知识渊博的科技信息助手。"
                "基于以下参考资料回答用户的问题。"
                "如果参考资料中没有相关信息，请基于你的知识回答，但要说明。"
                "使用中文回答。"
            ),
        },
    ]

    if history:
        messages.extend(history[-6:])

    messages.append({
        "role": "user",
        "content": f"参考资料：\n{context_text}\n\n问题：{question}",
    })

    return await _call_qwen(messages, temperature=0.5, max_tokens=2000, stream=True)
