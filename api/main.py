"""
RetailIQ API — FastAPI 後端

啟動方式：
    cd retail-iq
    source .env
    pip install -r api/requirements.txt
    uvicorn api.main:app --reload --port 8000

API 文件：
    http://localhost:8000/docs（Swagger UI）
    http://localhost:8000/redoc（ReDoc）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import products, scripts_gen, ingest, review

app = FastAPI(
    title="RetailIQ API",
    description="門市銷售訓練系統後端 — 產品知識、腳本生成、Ingest 管理",
    version="0.1.0",
)

# CORS — 開發期全開放
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(scripts_gen.router, prefix="/api/scripts", tags=["Script Generator"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingest Pipeline"])
app.include_router(review.router, prefix="/api/review-queue", tags=["Review Queue"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
