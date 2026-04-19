import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.nm import is_mock

router = APIRouter(prefix="/api/speedtest", tags=["speedtest"], dependencies=[Depends(current_user)])

HISTORY_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "speedtest_history.json"
MAX_HISTORY = 100

_lock = asyncio.Lock()


def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(h: list[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(h))
    tmp.replace(HISTORY_FILE)


async def _which(bin_name: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "which", bin_name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip() if proc.returncode == 0 else None


async def _is_ookla(path: str) -> bool:
    """Tell Ookla's `speedtest` (bandwidth in bytes) from Debian `speedtest-cli`
    (bandwidth in bits). We shadow-exec `--help` and look for Ookla's banner."""
    proc = await asyncio.create_subprocess_exec(
        path, "--version",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    text = (stdout + stderr).decode(errors="replace").lower()
    return "speedtest by ookla" in text or "ookla" in text


async def _run_ookla(path: str) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        path, "--format=json", "--accept-license", "--accept-gdpr",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=180)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="speedtest timed out") from None
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=stderr_b.decode(errors="replace").strip() or "speedtest failed",
        )
    data = json.loads(stdout_b)
    # Ookla bandwidth is bytes/s → bits/s → Mbps
    download_mbps = float(data.get("download", {}).get("bandwidth", 0)) * 8 / 1_000_000
    upload_mbps = float(data.get("upload", {}).get("bandwidth", 0)) * 8 / 1_000_000
    ping_ms = float(data.get("ping", {}).get("latency", 0))
    server = data.get("server", {}) or {}
    interface = data.get("interface", {}) or {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ping_ms": round(ping_ms, 2),
        "download_mbps": round(download_mbps, 2),
        "upload_mbps": round(upload_mbps, 2),
        "server": server.get("name"),
        "server_location": ", ".join(x for x in (server.get("location"), server.get("country")) if x),
        "client_ip": interface.get("externalIp"),
        "isp": data.get("isp"),
    }


async def _run_python_cli(path: str) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        path, "--json",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="speedtest timed out") from None
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=stderr_b.decode(errors="replace").strip() or "speedtest-cli failed",
        )
    data = json.loads(stdout_b)
    server = data.get("server") if isinstance(data.get("server"), dict) else {}
    client = data.get("client") if isinstance(data.get("client"), dict) else {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ping_ms": round(float(data.get("ping") or 0), 2),
        "download_mbps": round(float(data.get("download") or 0) / 1_000_000, 2),
        "upload_mbps": round(float(data.get("upload") or 0) / 1_000_000, 2),
        "server": server.get("sponsor"),
        "server_location": ", ".join(x for x in (server.get("name"), server.get("country")) if x),
        "client_ip": client.get("ip"),
        "isp": client.get("isp"),
    }


async def _run_speedtest() -> dict[str, Any]:
    # Prefer the Ookla binary if installed (handles both possible paths).
    for name in ("speedtest", "speedtest-cli"):
        path = await _which(name)
        if not path:
            continue
        if name == "speedtest" and await _is_ookla(path):
            return await _run_ookla(path)
        if name == "speedtest-cli":
            return await _run_python_cli(path)
        # Binary named "speedtest" that isn't Ookla — try Ookla flags anyway.
        return await _run_ookla(path)
    raise HTTPException(
        status_code=500,
        detail="no speedtest binary found — install `speedtest` (Ookla) or `speedtest-cli`",
    )


@router.get("/history")
async def history() -> dict[str, Any]:
    return {"runs": _load_history(), "running": _lock.locked()}


@router.post("/run")
async def run_test() -> dict[str, Any]:
    if is_mock():
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ping_ms": 15.2, "download_mbps": 123.4, "upload_mbps": 32.1,
            "server": "Mock ISP", "server_location": "Somewhere",
            "client_ip": "1.2.3.4", "isp": "Mock",
        }
        return result
    if _lock.locked():
        raise HTTPException(status_code=409, detail="a speedtest is already running")
    async with _lock:
        result = await _run_speedtest()
        h = _load_history()
        h.append(result)
        if len(h) > MAX_HISTORY:
            h = h[-MAX_HISTORY:]
        _save_history(h)
    return result
