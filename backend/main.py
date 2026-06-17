"""ClipForge FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from starlette.types import ASGIApp, Receive, Scope, Send
from backend.db import init_db
from backend.api import download, moments, process, publish
from backend.api.ws_router import ws_router
from backend.config import OUTPUT_DIR, DOWNLOADS_DIR

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


class AllowAllWebSocketMiddleware:
    """Strip Origin header from WebSocket requests so Starlette accepts them all.

    Starlette's built-in CORSMiddleware does not apply to WebSocket connections.
    Instead, Starlette compares the ``Origin`` header against the ``Host`` header
    during the WebSocket handshake and returns 403 if they differ.  Removing
    the Origin header entirely bypasses that check — safe for a localhost-only
    tool.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            scope["headers"] = [
                (k, v) for k, v in scope.get("headers", [])
                if k.lower() != b"origin"
            ]
        await self.app(scope, receive, send)


app = FastAPI(
    title="ClipForge API",
    description="Local video clip processing and publishing tool",
    version="1.0.0",
    lifespan=lifespan,
)

# WebSocket middleware — must be the OUTERMOST layer (added first)
app.add_middleware(AllowAllWebSocketMiddleware)

# HTTP CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routes — prefix /api
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(moments.router, prefix="/api", tags=["moments"])
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(publish.router, prefix="/api", tags=["publish"])

# WebSocket routes — NO prefix, paths are /ws/download/{id} etc.
app.include_router(ws_router, tags=["websocket"])

# Static file serving
try:
    app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="output_files")
    app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
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
