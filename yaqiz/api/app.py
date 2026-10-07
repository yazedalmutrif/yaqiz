"""FastAPI application factory: API under /api, voices under /voices, the dashboard SPA at /."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import Settings, get_settings
from ..context import Context
from . import routes_cameras, routes_events, routes_site, routes_system

log = logging.getLogger("yaqiz.api")


async def _heat_loop(ctx: Context) -> None:
    while True:
        try:
            ctx.bus.publish({"type": "heat", "heat": await run_in_threadpool(ctx.heat_now)})
        except Exception:  # noqa: BLE001
            log.exception("heat update failed")
        await asyncio.sleep(60)


def _mount_spa(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        @app.get("/", include_in_schema=False)
        def placeholder() -> HTMLResponse:
            return HTMLResponse("<!doctype html><meta charset=utf-8><title>Yaqiz</title>"
                                "<p>Yaqiz API is running. Build the dashboard: <code>cd app &amp;&amp; npm run build</code>"
                                " · API docs: <a href='/api/docs'>/api/docs</a></p>")
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    ctx = Context(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN202
        ctx.bus.attach(asyncio.get_running_loop())
        closed = await run_in_threadpool(ctx.store.close_orphan_events)
        if closed:
            logging.getLogger("yaqiz").info("closed %d events left open by a previous run", closed)
        if settings.start_workers:
            await run_in_threadpool(ctx.manager.start_all)
        task = asyncio.create_task(_heat_loop(ctx)) if settings.start_workers else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            await run_in_threadpool(ctx.manager.stop_all)

    app = FastAPI(title="Yaqiz API", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.ctx = ctx
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    for r in (routes_system.router, routes_site.router, routes_cameras.router, routes_events.router):
        app.include_router(r, prefix="/api")
    settings.voices_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/voices", StaticFiles(directory=settings.voices_dir), name="voices")
    _mount_spa(app, settings.app_dist)
    return app
