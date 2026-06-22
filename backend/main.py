"""ClipForge FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from backend.db import init_db
from backend.api import download, moments, process, publish, session, upload
from backend.api import moments_gpu
from backend.config import OUTPUT_DIR, DOWNLOADS_DIR, BANNERS_DIR

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down ClipForge")


app = FastAPI(
    title="ClipForge API",
    description="Local video clip processing and publishing tool",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow all origins (needed for local dev + VPN scenarios)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes (REST + WebSocket) are under /api prefix:
#   REST:      POST /api/download, POST /api/moments, etc.
#   WebSocket: ws://host:8000/api/ws/download/{id}
#              ws://host:8000/api/ws/moments/{id}
#              ws://host:8000/api/ws/process/{id}
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(moments.router, prefix="/api", tags=["moments"])
app.include_router(moments_gpu.router, prefix="/api", tags=["gpu"])
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(publish.router, prefix="/api", tags=["publish"])
app.include_router(session.router, prefix="/api", tags=["session"])
app.include_router(upload.router, prefix="/api", tags=["upload"])

# Static file serving
try:
    app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="output_files")
    app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
    app.mount("/files/banners", StaticFiles(directory=str(BANNERS_DIR)), name="banners")
except RuntimeError:
    pass


@app.get("/")
async def root():
    return {"message": "ClipForge API is running", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
