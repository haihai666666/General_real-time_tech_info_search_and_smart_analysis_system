"""
数据导入管道：将爬取的 JSON 文章导入 LightRAG 知识图谱。

用法：
    python -m crawler.ingest                          # 导入所有 raw 文章
    python -m crawler.ingest --source arxiv            # 只导入 arxiv 来源
    python -m crawler.ingest --limit 10                # 限制导入数量
    python -m crawler.ingest --api-url http://x:9622   # 指定 LightRAG API
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("crawler.ingest")

DATA_DIR = Path(
    os.getenv(
        "CRAWLER_DATA_DIR",
        str(Path(__file__).resolve().parent.parent / "data"),
    )
)
ARTICLES_DIR = DATA_DIR / "articles"
DEFAULT_API_URL = os.getenv("LIGHTRAG_API_URL", "http://localhost:9622")


def format_article_for_rag(article: dict) -> str:
    """将单篇文章格式化为适合 RAG 索引的纯文本"""
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

    tags = article.get("tags", [])
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    url = article.get("url", "")
    if url:
        parts.append(f"URL: {url}")

    content = article.get("content", "").strip()
    if content:
        parts.append(f"\n{content}")

    return "\n".join(parts)


def load_articles(source: str = None, limit: int = None) -> list[dict]:
    """从 JSON 文件加载文章"""
    index_file = ARTICLES_DIR / "index.json"
    if not index_file.exists():
        logger.warning("No index.json found at %s", index_file)
        return []

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    articles = []
    for entry in index:
        if entry.get("status") != "raw":
            continue
        if source and entry.get("source") != source:
            continue

        article_file = (
            ARTICLES_DIR / entry.get("source", "unknown") / f"{entry['id']}.json"
        )
        if not article_file.exists():
            continue

        with open(article_file, "r", encoding="utf-8") as f:
            article = json.load(f)
        articles.append(article)

        if limit and len(articles) >= limit:
            break

    return articles


def update_article_status(article_id: str, status: str):
    """更新文章在 index.json 中的状态"""
    index_file = ARTICLES_DIR / "index.json"
    if not index_file.exists():
        return

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    for entry in index:
        if entry["id"] == article_id:
            entry["status"] = status
            break

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def ingest_to_lightrag(articles: list[dict], api_url: str, batch_size: int = 5) -> dict:
    """将文章批量导入 LightRAG"""
    stats = {"total": len(articles), "success": 0, "failed": 0, "skipped": 0}

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        texts = []
        ids = []
        file_paths = []

        for article in batch:
            text = format_article_for_rag(article)
            if len(text.strip()) < 50:
                stats["skipped"] += 1
                continue
            texts.append(text)
            ids.append(article.get("id", ""))
            file_paths.append(article.get("url", ""))

        if not texts:
            continue

        try:
            token = os.getenv("LIGHTRAG_API_TOKEN", "")
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            # Upload each article separately
            for idx, text in enumerate(texts):
                resp = requests.post(
                    f"{api_url}/documents/text",
                    json={"text": text},
                    headers=headers,
                    timeout=300,
                )

                if resp.status_code in (200, 201):
                    stats["success"] += 1
                    update_article_status(batch[idx]["id"], "ingested")
                    logger.info(
                        "Article %d/%d ingested successfully: %s",
                        i + idx + 1,
                        len(articles),
                        batch[idx].get("title", "")[:50],
                    )
                else:
                    stats["failed"] += 1
                    logger.error(
                        "Article %d/%d failed (HTTP %d): %s",
                        i + idx + 1,
                        len(articles),
                        resp.status_code,
                        resp.text[:200],
                    )

                # Small delay between uploads
                if idx < len(texts) - 1:
                    time.sleep(0.5)
        except requests.exceptions.RequestException as e:
            stats["failed"] += len(texts)
            logger.error("Batch %d-%d request error: %s", i, i + len(batch), e)

        if i + batch_size < len(articles):
            time.sleep(1)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import crawled articles into LightRAG"
    )
    parser.add_argument(
        "--source", type=str, default=None, help="Filter by source (e.g. arxiv)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max articles to import"
    )
    parser.add_argument(
        "--api-url", type=str, default=DEFAULT_API_URL, help="LightRAG API URL"
    )
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Batch size for import"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show articles without importing"
    )
    args = parser.parse_args()

    logger.info("Loading articles from %s", ARTICLES_DIR)
    articles = load_articles(source=args.source, limit=args.limit)
    logger.info("Found %d articles to import", len(articles))

    if not articles:
        logger.info("No articles to import. Run a spider first.")
        return

    if args.dry_run:
        for a in articles:
            print(f"  [{a.get('source')}] {a.get('title', '')[:80]}")
        print(f"\nTotal: {len(articles)} articles (dry run, not imported)")
        return

    logger.info("Importing to LightRAG at %s", args.api_url)
    stats = ingest_to_lightrag(articles, args.api_url, batch_size=args.batch_size)
    logger.info(
        "Import complete: %d success, %d failed, %d skipped (total: %d)",
        stats["success"],
        stats["failed"],
        stats["skipped"],
        stats["total"],
    )


if __name__ == "__main__":
    main()
