from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.nm import is_mock, run_cmd

router = APIRouter(prefix="/api/ssh", tags=["ssh"], dependencies=[Depends(current_user)])

SERVICE = "ssh.service"


async def _probe(cmd: str) -> str:
    r = await run_cmd("systemctl", cmd, SERVICE, check=False)
    return r.stdout.strip()


@router.get("")
async def status() -> dict[str, Any]:
    if is_mock():
        return {"enabled": True, "active": True, "port": 22}
    return {
        "enabled": await _probe("is-enabled") == "enabled",
        "active": await _probe("is-active") == "active",
        "port": 22,
    }


@router.post("/enable")
async def enable() -> dict[str, str]:
    if is_mock():
        return {"ok": "1"}
    r = await run_cmd("sudo", "-n", "/bin/systemctl", "enable", "--now", SERVICE, check=False)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "enable failed")
    return {"ok": "1"}


@router.post("/disable")
async def disable() -> dict[str, str]:
    if is_mock():
        return {"ok": "1"}
    r = await run_cmd("sudo", "-n", "/bin/systemctl", "disable", "--now", SERVICE, check=False)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "disable failed")
    return {"ok": "1"}
