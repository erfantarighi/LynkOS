import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.auth import current_user
from app.models import OkResponse
from app.snapshot import (
    SNAPSHOT_VERSION,
    SavedDdns,
    SavedHotspot,
    SavedPppoe,
    SavedRoute,
    SavedVlan,
    Snapshot,
    apply_all,
    capture_live,
    load_snapshot,
    save_snapshot,
)

router = APIRouter(prefix="/api/snapshot", tags=["snapshot"], dependencies=[Depends(current_user)])


def _redact(snap_dict: dict[str, Any]) -> dict[str, Any]:
    if snap_dict.get("hotspot"):
        snap_dict["hotspot"] = {**snap_dict["hotspot"], "passphrase": "••••••••"}
    if snap_dict.get("pppoe"):
        snap_dict["pppoe"] = {**snap_dict["pppoe"], "password": "••••••••"}
    return snap_dict


@router.get("")
async def get_snapshot() -> dict[str, Any]:
    snap = load_snapshot()
    return _redact({
        "version": snap.version,
        "vlans": [asdict(v) for v in snap.vlans],
        "routes": [asdict(r) for r in snap.routes],
        "hotspot": asdict(snap.hotspot) if snap.hotspot else None,
        "pppoe": asdict(snap.pppoe) if snap.pppoe else None,
    })


@router.post("/apply")
async def apply_snapshot() -> dict[str, Any]:
    return await apply_all()


@router.post("/capture")
async def capture_snapshot() -> dict[str, Any]:
    """Scan live system state and save it to the snapshot (overwrites captured
    sections; PPPoE password is not read from chap-secrets)."""
    return await capture_live()


@router.delete("", response_model=OkResponse)
async def clear_snapshot() -> OkResponse:
    save_snapshot(Snapshot())
    return OkResponse(detail="snapshot cleared")


@router.get("/export")
async def export_snapshot() -> Response:
    """Download the full snapshot as a JSON file. Contains secrets (API tokens,
    PPPoE/hotspot passwords) — keep the file safe."""
    snap = load_snapshot()
    payload = {
        "version": snap.version,
        "vlans": [asdict(v) for v in snap.vlans],
        "routes": [asdict(r) for r in snap.routes],
        "hotspot": asdict(snap.hotspot) if snap.hotspot else None,
        "pppoe": asdict(snap.pppoe) if snap.pppoe else None,
        "ddns": asdict(snap.ddns) if snap.ddns else None,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="lynkos-snapshot-{stamp}.json"'},
    )


@router.post("/import", response_model=OkResponse)
async def import_snapshot(file: UploadFile = File(...)) -> OkResponse:
    """Upload a previously exported snapshot. Replaces the current one.
    Apply is NOT automatic — click "Re-apply now" to push it to the system."""
    raw = await file.read()
    if len(raw) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="expected a JSON object")
    version = data.get("version")
    if version != SNAPSHOT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported snapshot version: {version} (expected {SNAPSHOT_VERSION})",
        )
    try:
        snap = Snapshot(
            version=version,
            vlans=[SavedVlan(**v) for v in (data.get("vlans") or [])],
            routes=[SavedRoute(**r) for r in (data.get("routes") or [])],
            hotspot=SavedHotspot(**data["hotspot"]) if data.get("hotspot") else None,
            pppoe=SavedPppoe(**data["pppoe"]) if data.get("pppoe") else None,
            ddns=SavedDdns(**data["ddns"]) if data.get("ddns") else None,
        )
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"invalid snapshot structure: {e}") from e
    save_snapshot(snap)
    return OkResponse(
        detail=f"snapshot imported — {len(snap.vlans)} VLANs, {len(snap.routes)} routes"
    )
