"""APK Analysis Microservice — FastAPI application."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kavalx APK Analysis Service",
    description="Static analysis, dynamic sandbox, GenAI deobfuscation, and meta-classification for Android APKs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, tags=["APK Analysis"])


@app.on_event("startup")
async def startup():
    logger.info(f"APK Analysis Service starting on port {settings.PORT}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
