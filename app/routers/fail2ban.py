import ipaddress
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.nm import is_mock, run_cmd

router = APIRouter(prefix="/api/fail2ban", tags=["fail2ban"], dependencies=[Depends(current_user)])

HELPER = "/usr/local/sbin/lynkos-fail2ban"


def _parse_status(text: str) -> dict[str, Any]:
    def m(pattern: str, default: str = "") -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default

    banned_raw = m(r"Banned IP list:\s*(.*)")
    return {
        "enabled": True,
        "currently_failed": int(m(r"Currently failed:\s*(\d+)", "0")),
        "total_failed": int(m(r"Total failed:\s*(\d+)", "0")),
        "currently_banned": int(m(r"Currently banned:\s*(\d+)", "0")),
        "total_banned": int(m(r"Total banned:\s*(\d+)", "0")),
        "banned_ips": [ip for ip in banned_raw.split() if ip],
    }


async def _jail_status(jail: str) -> dict[str, Any]:
    r = await run_cmd("sudo", "-n", HELPER, "status", jail, check=False)
    if r.returncode != 0:
        return {"enabled": False, "error": (r.stderr.strip() or r.stdout.strip() or "unavailable")}
    return _parse_status(r.stdout)


@router.get("/status")
async def status() -> dict[str, Any]:
    if is_mock():
        return {
            "jails": {
                "lynkos": {"enabled": True, "currently_banned": 0, "total_banned": 3, "currently_failed": 0, "total_failed": 12, "banned_ips": []},
                "sshd": {"enabled": False, "error": "jail not found"},
            },
        }
    return {
        "jails": {
            "lynkos": await _jail_status("lynkos"),
            "sshd": await _jail_status("sshd"),
        }
    }


@router.post("/unban")
async def unban(jail: str, ip: str) -> dict[str, str]:
    if not re.match(r"^[A-Za-z0-9_-]+$", jail):
        raise HTTPException(status_code=400, detail="invalid jail name")
    try:
        ipaddress.ip_address(ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid IP: {e}") from e
    if is_mock():
        return {"ok": "1"}
    r = await run_cmd("sudo", "-n", HELPER, "unban", jail, ip, check=False)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "unban failed")
    return {"ok": "1"}


@router.get("/logs")
async def logs(n: int = 100) -> dict[str, Any]:
    n = max(1, min(500, n))
    if is_mock():
        return {"lines": ["2026-04-19 00:00:00 fail2ban.jail [123]: INFO Jail 'lynkos' started"]}
    r = await run_cmd("sudo", "-n", HELPER, "logs", str(n), check=False)
    if r.returncode != 0:
        return {"lines": [], "error": r.stderr.strip() or "unavailable"}
    return {"lines": [ln for ln in r.stdout.splitlines() if ln.strip()]}
