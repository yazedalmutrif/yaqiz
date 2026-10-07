"""Cameras, calibration (plan ↔ image homography) and live streams."""
from __future__ import annotations

import asyncio

import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from ..geometry import calibration_coverage, fit_homography
from ..models import Camera
from ..serialize import camera_dict
from ..vision.worker import zone_polygons_for_camera
from .deps import CtxDep
from .schemas import CalibrationIn, CameraIn, CameraPatch

router = APIRouter(tags=["cameras"])


def _cam_or_404(ctx, camera_id: int) -> Camera:  # noqa: ANN001
    cam = ctx.store.get_camera(camera_id)
    if cam is None:
        raise HTTPException(404, "الكاميرا غير موجودة")
    return cam


@router.get("/cameras")
def list_cameras(ctx: CtxDep) -> list[dict]:
    return [camera_dict(c, ctx.manager.status(c.id)) for c in ctx.store.list_cameras()]


@router.post("/cameras", status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraIn, ctx: CtxDep) -> dict:
    cam = ctx.store.save_camera(Camera(**body.model_dump()))
    if cam.enabled and ctx.settings.start_workers:
        ctx.manager.start(cam.id)
    return camera_dict(cam, ctx.manager.status(cam.id))


@router.put("/cameras/{camera_id}")
def update_camera(camera_id: int, body: CameraPatch, ctx: CtxDep) -> dict:
    before = _cam_or_404(ctx, camera_id)
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    cam = ctx.store.update_camera(camera_id, **fields)
    if ctx.settings.start_workers:
        if not cam.enabled:
            ctx.manager.stop(camera_id)
        elif cam.source != before.source or not before.enabled:
            ctx.manager.restart(camera_id)
        else:
            ctx.manager.reload(camera_id)
    return camera_dict(cam, ctx.manager.status(camera_id))


@router.delete("/cameras/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, ctx: CtxDep) -> Response:
    _cam_or_404(ctx, camera_id)
    ctx.manager.stop(camera_id)
    ctx.store.delete_camera(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cameras/{camera_id}/start")
def start_camera(camera_id: int, ctx: CtxDep) -> dict:
    cam = ctx.store.update_camera(_cam_or_404(ctx, camera_id).id, enabled=True)
    ctx.manager.start(camera_id)
    return camera_dict(cam, ctx.manager.status(camera_id))


@router.post("/cameras/{camera_id}/stop")
def stop_camera(camera_id: int, ctx: CtxDep) -> dict:
    cam = ctx.store.update_camera(_cam_or_404(ctx, camera_id).id, enabled=False)
    ctx.manager.stop(camera_id)
    return camera_dict(cam, None)


@router.get("/cameras/{camera_id}/frame.jpg")
def camera_frame(camera_id: int, ctx: CtxDep) -> Response:
    _cam_or_404(ctx, camera_id)
    worker = ctx.manager.get(camera_id)
    jpg = worker.snapshot_jpeg() if worker else None
    if jpg is None:
        raise HTTPException(409, "الكاميرا غير مشغّلة أو لم تصل منها صورة بعد")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/cameras/{camera_id}/stream.mjpg")
async def camera_stream(camera_id: int, request: Request, ctx: CtxDep) -> StreamingResponse:
    _cam_or_404(ctx, camera_id)
    period = 1.0 / max(ctx.settings.stream_fps, 1.0)

    async def frames():  # noqa: ANN202
        last = -1
        while not await request.is_disconnected():
            worker = ctx.manager.get(camera_id)
            if worker is not None:
                jpg, seq = worker.latest_jpeg()
                if jpg is not None and seq != last:
                    last = seq
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            await asyncio.sleep(period)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.put("/cameras/{camera_id}/calibration")
def calibrate(camera_id: int, body: CalibrationIn, ctx: CtxDep) -> dict:
    cam = _cam_or_404(ctx, camera_id)
    try:
        H, err = fit_homography([p.plan for p in body.pairs], [p.image for p in body.pairs])
    except ValueError as exc:
        raise HTTPException(422, f"تعذّرت المعايرة: {exc}") from exc
    pairs = [{"plan": list(p.plan), "image": list(p.image)} for p in body.pairs]
    cam = ctx.store.update_camera(camera_id, homography=H.tolist(), calib_pairs=pairs, calib_error_px=round(err, 2))
    ctx.manager.reload(camera_id)
    w, h = cam.frame_width or 1280, cam.frame_height or 720
    coverage = calibration_coverage([p["plan"] for p in pairs])
    in_view = zone_polygons_for_camera(np.asarray(H), ctx.store.list_zones(), w, h, coverage)
    return {"camera": camera_dict(cam, ctx.manager.status(camera_id)), "error_px": round(err, 2),
            "zones_in_view": {str(zid): pts.round(1).tolist() for zid, pts in in_view.items()}}


@router.get("/cameras/{camera_id}/calibration/preview")
def calibration_preview(camera_id: int, ctx: CtxDep) -> dict:
    """Zones as this camera sees them (clipped to the calibrated ground area), in image pixels."""
    cam = _cam_or_404(ctx, camera_id)
    if not cam.homography:
        return {"zones_in_view": {}, "error_px": None}
    w, h = cam.frame_width or 1280, cam.frame_height or 720
    coverage = calibration_coverage([p["plan"] for p in (cam.calib_pairs or [])])
    in_view = zone_polygons_for_camera(np.asarray(cam.homography), ctx.store.list_zones(), w, h, coverage)
    return {"zones_in_view": {str(zid): pts.round(1).tolist() for zid, pts in in_view.items()},
            "error_px": cam.calib_error_px}


@router.delete("/cameras/{camera_id}/calibration", status_code=status.HTTP_204_NO_CONTENT)
def clear_calibration(camera_id: int, ctx: CtxDep) -> Response:
    _cam_or_404(ctx, camera_id)
    ctx.store.update_camera(camera_id, homography=None, calib_pairs=None, calib_error_px=None)
    ctx.manager.reload(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
