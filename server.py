"""
聚合分析平台 - 后端服务入口

整合 LightRAG 原有 API + 爬虫管理 API + 智能分析 API
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("server")

app = FastAPI(
    title="科技信息聚合分析平台",
    description="实时科技信息采集、知识图谱构建与智能分析系统",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9622", "http://127.0.0.1:9622", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from crawler.api import router as crawler_router
from algorithm.api import router as analysis_router

app.include_router(crawler_router)
app.include_router(analysis_router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "tech-info-platform",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("PLATFORM_HOST", "0.0.0.0")
    port = int(os.getenv("PLATFORM_PORT", "8000"))
    logger.info("Starting platform server on %s:%d", host, port)
    uvicorn.run("server:app", host=host, port=port, reload=True)
