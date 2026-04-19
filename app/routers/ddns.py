from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.ddns import runner
from app.models import DdnsConfig, OkResponse
from app.snapshot import SavedDdns, load_snapshot, set_ddns

router = APIRouter(prefix="/api/ddns", tags=["ddns"], dependencies=[Depends(current_user)])


def _redacted(cfg: SavedDdns | None) -> dict[str, Any]:
    if not cfg:
        return {"enabled": False, "api_token": "", "zone": "", "hostnames": [], "proxied": False, "interval_seconds": 60, "last_ip": ""}
    d = cfg.__dict__.copy()
    if d.get("api_token"):
        d["api_token"] = "••••••••" + d["api_token"][-4:]
    return d


@router.get("")
async def get_ddns() -> dict[str, Any]:
    snap = load_snapshot()
    return {"config": _redacted(snap.ddns), "state": runner.snapshot_state()}


@router.post("", response_model=OkResponse)
async def save_ddns(cfg: DdnsConfig) -> OkResponse:
    # Preserve the existing token if the client sent back the redacted mask.
    prev = load_snapshot().ddns
    token = cfg.api_token
    if prev and token.startswith("••••••••"):
        token = prev.api_token
    if cfg.enabled and not token:
        raise HTTPException(status_code=400, detail="api_token required when enabled")
    set_ddns(SavedDdns(
        enabled=cfg.enabled,
        api_token=token,
        zone=cfg.zone.strip(),
        hostnames=[h.strip() for h in cfg.hostnames if h.strip()],
        proxied=cfg.proxied,
        interval_seconds=cfg.interval_seconds,
        last_ip=prev.last_ip if prev else "",
    ))
    # Reset resolved zone cache in case zone changed.
    runner.state.zone_id = None
    await runner.start() if cfg.enabled else await runner.stop()
    return OkResponse(detail="ddns config saved")


@router.post("/update")
async def update_now(_: Annotated[str, Depends(current_user)]) -> dict[str, Any]:
    state = await runner.trigger_now()
    return runner.snapshot_state() if state else {}
