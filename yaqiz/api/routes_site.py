"""Site, site plan and zones."""
from __future__ import annotations

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from ..models import Zone
from ..serialize import zone_dict
from .deps import CtxDep
from .schemas import SiteIn, ZoneIn, ZonePatch

router = APIRouter(tags=["site"])
MAX_PLAN_BYTES = 15 * 1024 * 1024
MAX_PLAN_SIDE = 4000


def _site_dict(site) -> dict:  # noqa: ANN001
    return {"id": site.id, "name": site.name, "lat": site.lat, "lon": site.lon,
            "plan_url": "/api/site/plan" if site.plan_file else None,
            "plan_width": site.plan_width, "plan_height": site.plan_height,
            "plan_version": int(site.updated_at.timestamp())}


@router.get("/site")
def get_site(ctx: CtxDep) -> dict:
    return _site_dict(ctx.store.get_site())


@router.put("/site")
def put_site(body: SiteIn, ctx: CtxDep) -> dict:
    return _site_dict(ctx.store.update_site(**body.model_dump()))


@router.post("/site/plan")
def upload_plan(ctx: CtxDep, file: UploadFile = File(...)) -> dict:
    data = file.file.read(MAX_PLAN_BYTES + 1)
    if len(data) > MAX_PLAN_BYTES:
        raise HTTPException(413, "حجم الملف أكبر من 15 ميغابايت")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, "الملف ليس صورة صالحة (PNG أو JPG)")
    h, w = img.shape[:2]
    if max(h, w) > MAX_PLAN_SIDE:
        s = MAX_PLAN_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    ctx.settings.site_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ctx.settings.site_dir / "plan.png"), img)
    before = ctx.store.get_site()
    site = ctx.store.update_site(plan_file="plan.png", plan_width=w, plan_height=h)
    out = _site_dict(site)
    if ctx.store.list_zones() and (before.plan_width, before.plan_height) != (w, h):
        out["warning"] = "تغيّرت أبعاد المخطط؛ راجع مواقع المناطق ومعايرة الكاميرات."
    return out


@router.get("/site/plan")
def get_plan(ctx: CtxDep) -> FileResponse:
    site = ctx.store.get_site()
    path = ctx.settings.site_dir / (site.plan_file or "")
    if not site.plan_file or not path.is_file():
        raise HTTPException(404, "لم يُرفع مخطط للموقع بعد")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.get("/zones")
def list_zones(ctx: CtxDep) -> list[dict]:
    return [zone_dict(z) for z in ctx.store.list_zones()]


@router.post("/zones", status_code=status.HTTP_201_CREATED)
def create_zone(body: ZoneIn, ctx: CtxDep) -> dict:
    data = body.model_dump()
    data["points"] = [list(p) for p in data["points"]]
    zone = ctx.store.save_zone(Zone(**data))
    ctx.manager.reload_all()
    return zone_dict(zone)


@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, body: ZonePatch, ctx: CtxDep) -> dict:
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if "points" in fields:
        fields["points"] = [list(p) for p in fields["points"]]
    zone = ctx.store.update_zone(zone_id, **fields)
    if zone is None:
        raise HTTPException(404, "المنطقة غير موجودة")
    ctx.manager.reload_all()
    return zone_dict(zone)


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: int, ctx: CtxDep) -> Response:
    if not ctx.store.delete_zone(zone_id):
        raise HTTPException(404, "المنطقة غير موجودة")
    ctx.manager.reload_all()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
