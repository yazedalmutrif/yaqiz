"""API tests: site, zones, calibration, events, risk, report, settings, heat, voices and the WebSocket."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from yaqiz.api.app import create_app
from yaqiz.config import Settings
from yaqiz.models import Camera, Event


@pytest.fixture()
def client(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", start_workers=False, app_dist=tmp_path / "no-dist",
                        voices_dir=tmp_path / "voices")
    app = create_app(settings)
    app.state.ctx.weather._fetch = lambda lat, lon: (40.0, 30.0)  # no network in tests
    with TestClient(app) as c:
        c.ctx = app.state.ctx
        yield c


ZONE = {"name": "الحفريات", "kind": "no_entry", "points": [[0, 0], [100, 0], [100, 50], [0, 50]], "outdoor": True}


def test_site_and_zone_crud(client):
    assert client.get("/api/site").json()["plan_url"] is None
    r = client.post("/api/zones", json=ZONE)
    assert r.status_code == 201
    zid = r.json()["id"]
    assert client.put(f"/api/zones/{zid}", json={"active": False}).json()["active"] is False
    assert len(client.get("/api/zones").json()) == 1
    bad = client.post("/api/zones", json={**ZONE, "points": [[0, 0], [1, 1], [2, 2]]})
    assert bad.status_code == 422
    assert client.delete(f"/api/zones/{zid}").status_code == 204
    assert client.get("/api/zones").json() == []


def test_plan_upload_rejects_non_images(client):
    r = client.post("/api/site/plan", files={"file": ("plan.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_calibration_returns_error_and_zone_preview(client):
    client.post("/api/zones", json={**ZONE, "points": [[1040, 200], [1100, 200], [1100, 650], [1040, 650]]})
    cam = client.ctx.store.save_camera(Camera(name="CAM", source="0", enabled=False, frame_width=1280, frame_height=720))
    pairs = [{"plan": [1100, 200], "image": [748.8, 266.4]}, {"plan": [1100, 650], "image": [1273.6, 266.4]},
             {"plan": [1040, 650], "image": [1273.6, 338.4]}, {"plan": [1040, 200], "image": [748.8, 338.4]}]
    r = client.put(f"/api/cameras/{cam.id}/calibration", json={"pairs": pairs})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error_px"] < 0.01 and body["camera"]["calibrated"]
    assert list(body["zones_in_view"]) == ["1"]
    bad = client.put(f"/api/cameras/{cam.id}/calibration",
                     json={"pairs": [{"plan": [i, i], "image": [i, i]} for i in range(4)]})
    assert bad.status_code == 422
    assert client.get(f"/api/cameras/{cam.id}/frame.jpg").status_code == 409


def test_events_ack_risk_and_report(client):
    store = client.ctx.store
    zid = client.post("/api/zones", json=ZONE).json()["id"]
    now = datetime.now(timezone.utc)
    ev = store.add_event(Event(ts=now, kind="zone_intrusion", severity="critical", zone_id=zid, camera_id=1))
    store.add_event(Event(ts=now, kind="ppe_missing", severity="warning", item="helmet", camera_id=1))
    r = client.get("/api/events", params={"kind": "zone_intrusion"}).json()
    assert r["total"] == 1 and r["items"][0]["id"] == ev.id
    assert client.get("/api/events", params={"kind": "nope"}).status_code == 422
    assert client.post(f"/api/events/{ev.id}/ack").json()["acknowledged"] is True
    assert client.get("/api/events", params={"unacked": True}).json()["total"] == 1
    risk = client.get("/api/risk", params={"shift": "full"}).json()
    assert len(risk["hours"]) == 24 and risk["top"]["zone_id"] == zid
    assert client.get("/api/risk").json()["hours"] == list(range(6, 18))  # 06:00–18:00 = 12 hourly columns
    report = client.get("/api/report").json()
    assert report["totals"] == {"events": 2, "critical": 1, "warning": 1, "acknowledged": 1}
    assert client.get(f"/api/events/{ev.id}/snapshot.jpg").status_code == 404


def test_settings_roundtrip_and_validation(client):
    rt = client.get("/api/settings").json()
    rt["man_down_s"] = 7.5
    assert client.put("/api/settings", json=rt).json()["man_down_s"] == 7.5
    assert client.put("/api/settings", json={**rt, "voice_languages": ["xx"]}).status_code == 422


def test_heat_manual_override(client):
    h = client.put("/api/heat/manual", json={"temperature_c": 35, "humidity": 50}).json()
    assert h["source"] == "manual" and h["heat_index_c"] == pytest.approx(40.7, abs=0.2) and h["category"] == 3
    assert client.delete("/api/heat/manual").json()["source"] == "open-meteo"


def test_voices_manifest_and_websocket_hello(client):
    m = client.get("/api/voices").json()
    assert {l["code"] for l in m["languages"]} == {"ar", "en", "ur", "hi", "bn"}
    assert m["phrases"]["zone"]["ar"]["url"] == "/voices/zone_ar.mp3"
    with client.websocket_connect("/api/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
