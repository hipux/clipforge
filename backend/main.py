"""ClipForge FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from starlette.types import ASGIApp, Receive, Scope, Send
from backend.db import init_db
from backend.api import download, moments, process, publish
from backend.config import OUTPUT_DIR, DOWNLOADS_DIR

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )
    
    # Startup: Initialize database
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown: cleanup if needed
    logger.info("Shutting down ClipForge")


class WebSocketCORSMiddleware:
    """Allow WebSocket connections from any origin.
    
    CORSMiddleware does NOT apply to WebSocket connections in Starlette.
    This middleware fixes Origin header issues for WebSocket connections.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "websocket":
            # Starlette checks Origin against Host - set them to match
            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"localhost:8000")
            # Remove existing origin and add one that matches the host
            scope["headers"] = [
                (k, v) for k, v in scope.get("headers", [])
                if k.lower() != b"origin"
            ] + [(b"origin", b"http://" + host)]
        await self.app(scope, receive, send)


app = FastAPI(
    title="ClipForge API",
    description="Local video clip processing and publishing tool",
    version="1.0.0",
    lifespan=lifespan
)

# WebSocket CORS middleware - MUST come BEFORE CORSMiddleware
app.add_middleware(WebSocketCORSMiddleware)

# CORS middleware - allow all origins (needed for VPN scenarios)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(moments.router, prefix="/api", tags=["moments"])
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(publish.router, prefix="/api", tags=["publish"])

# Serve static files (processed clips and downloads)
try:
    app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="output_files")
    app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
except RuntimeError:
    # Directories might not exist yet
    pass


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ClipForge API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
