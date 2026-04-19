from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adblock import (
    DEFAULT_BLOCKLISTS,
    current_entry_count,
    disable_on_hotspot,
    enable_on_hotspot,
    update as run_update,
)
from app.auth import current_user
from app.models import AdblockConfig, OkResponse
from app.nm import is_mock
from app.snapshot import SavedAdblock, load_snapshot, set_adblock

router = APIRouter(prefix="/api/adblock", tags=["adblock"], dependencies=[Depends(current_user)])


def _load_or_default() -> SavedAdblock:
    snap = load_snapshot()
    if snap.adblock is None:
        return SavedAdblock(blocklists=list(DEFAULT_BLOCKLISTS))
    # Ensure defaults if empty
    if not snap.adblock.blocklists:
        snap.adblock.blocklists = list(DEFAULT_BLOCKLISTS)
    return snap.adblock


@router.get("")
async def status() -> dict[str, Any]:
    cfg = _load_or_default()
    return {
        "enabled": cfg.enabled,
        "blocklists": cfg.blocklists,
        "allowlist": cfg.allowlist,
        "entry_count": current_entry_count() if not is_mock() else cfg.entry_count,
        "last_update": cfg.last_update,
        "last_error": cfg.last_error,
    }


@router.post("", response_model=OkResponse)
async def save_config(cfg: AdblockConfig) -> OkResponse:
    current = _load_or_default()
    blocklists = [u.strip() for u in cfg.blocklists if u.strip()] or list(DEFAULT_BLOCKLISTS)
    allowlist = [d.strip().lower() for d in cfg.allowlist if d.strip()]
    current.blocklists = blocklists
    current.allowlist = allowlist
    set_adblock(current)
    return OkResponse(detail="adblock config saved")


@router.post("/update", response_model=OkResponse)
async def update_now() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) updated")
    cfg = _load_or_default()
    try:
        count, failed, ts = await run_update(cfg.blocklists, cfg.allowlist)
    except Exception as e:
        cfg.last_error = str(e)
        set_adblock(cfg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    cfg.entry_count = count
    cfg.last_update = ts
    cfg.last_error = "; ".join(failed) if failed else ""
    set_adblock(cfg)
    return OkResponse(detail=f"{count} domains blocked"
                             + (f", {len(failed)} list(s) failed" if failed else ""))


@router.post("/enable", response_model=OkResponse)
async def enable() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) enabled")
    cfg = _load_or_default()
    # Fetch lists first so the hosts file exists before NM dnsmasq re-launches.
    try:
        count, failed, ts = await run_update(cfg.blocklists, cfg.allowlist)
        await enable_on_hotspot()
    except Exception as e:
        cfg.last_error = str(e)
        set_adblock(cfg)
        raise HTTPException(status_code=500, detail=str(e)) from e
    cfg.enabled = True
    cfg.entry_count = count
    cfg.last_update = ts
    cfg.last_error = "; ".join(failed) if failed else ""
    set_adblock(cfg)
    return OkResponse(detail=f"adblock enabled — {count} domains blocked")


@router.post("/disable", response_model=OkResponse)
async def disable() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) disabled")
    cfg = _load_or_default()
    try:
        await disable_on_hotspot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    cfg.enabled = False
    set_adblock(cfg)
    return OkResponse(detail="adblock disabled")
