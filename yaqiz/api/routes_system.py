"""Health, heat, runtime settings, voice catalogue and the live WebSocket."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import __version__
from ..config import RuntimeSettings
from ..voice import manifest
from .deps import CtxDep
from .schemas import HeatManualIn

router = APIRouter(tags=["system"])


@lru_cache
def _gpu_name() -> str | None:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        mps = getattr(torch.backends, "mps", None)
        return "Apple GPU (MPS)" if mps is not None and mps.is_available() else None
    except Exception:  # noqa: BLE001
        return None


@router.get("/health")
def health(ctx: CtxDep) -> dict:
    ppe = ctx.ppe_loaded
    return {
        "status": "ok", "version": __version__,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cameras": [ctx.manager.status(c.id) or {"id": c.id, "name": c.name, "state": "stopped"}
                    for c in ctx.store.list_cameras()],
        "ppe_model": ppe.path.name if ppe else None,
        "capabilities": sorted(ppe.capabilities) if ppe else None,
        "gpu": _gpu_name() if ctx.settings.start_workers else None,
        "clients": ctx.bus.subscribers,
    }


@router.get("/heat")
def heat(ctx: CtxDep) -> dict:
    return ctx.heat_now()


@router.put("/heat/manual")
def heat_manual(body: HeatManualIn, ctx: CtxDep) -> dict:
    ctx.weather.set_manual(body.temperature_c, body.humidity)
    data = ctx.heat_now()
    ctx.bus.publish({"type": "heat", "heat": data})
    return data


@router.delete("/heat/manual")
def heat_auto(ctx: CtxDep) -> dict:
    ctx.weather.clear_manual()
    data = ctx.heat_now()
    ctx.bus.publish({"type": "heat", "heat": data})
    return data


@router.get("/settings")
def get_settings(ctx: CtxDep) -> RuntimeSettings:
    return ctx.store.get_runtime()


@router.put("/settings")
def put_settings(body: RuntimeSettings, ctx: CtxDep) -> RuntimeSettings:
    rt = ctx.store.put_runtime(body)
    ctx.manager.reload_all()
    return rt


@router.get("/voices")
def voices(ctx: CtxDep) -> dict:
    return manifest(ctx.settings.voices_dir)


@router.websocket("/ws")
async def live(websocket: WebSocket) -> None:
    ctx = websocket.app.state.ctx
    await websocket.accept()
    q = ctx.bus.subscribe()
    try:
        await websocket.send_json({"type": "hello", "version": __version__,
                                   "cameras": [ctx.manager.status(c.id) or {"id": c.id, "state": "stopped"}
                                               for c in ctx.store.list_cameras()]})
        while True:
            await websocket.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ctx.bus.unsubscribe(q)
