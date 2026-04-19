import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.config import Settings, get_settings
from app.models import OkResponse, PppoeConfig, PppoeStatus
from app.nm import NmcliError, is_mock, run_cmd
from app.snapshot import SavedPppoe, set_pppoe

router = APIRouter(prefix="/api/pppoe", tags=["pppoe"], dependencies=[Depends(current_user)])

PEER_NAME = "lynkos-wan"
PEER_FILE = Path(f"/etc/ppp/peers/{PEER_NAME}")

# Narrow whitelist — the helper script also validates, but reject early.
_SAFE = re.compile(r"^[A-Za-z0-9._@\-+]+$")
# Peer files set by `pppoeconf` traditionally use this name; surface them too.
LEGACY_PEERS = ("dsl-provider", "provider")


def _validate(value: str, field: str) -> None:
    if not _SAFE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid characters in {field}")


def _parse_peer_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    try:
        text = path.read_text()
    except PermissionError:
        return {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("plugin rp-pppoe.so"):
            parts = line.split()
            if len(parts) >= 3:
                data["interface"] = parts[2]
        elif line.startswith("user "):
            m = re.match(r'user\s+"?([^"\s]+)"?', line)
            if m:
                data["username"] = m.group(1)
        elif line.startswith("mtu "):
            parts = line.split()
            if len(parts) >= 2:
                data["mtu"] = parts[1]
    return data


def _discover_peer() -> tuple[str, Path, dict[str, str]]:
    """Return (name, path, parsed) for our peer or the first legacy peer found."""
    if PEER_FILE.exists():
        return PEER_NAME, PEER_FILE, _parse_peer_file(PEER_FILE)
    for name in LEGACY_PEERS:
        candidate = Path(f"/etc/ppp/peers/{name}")
        if candidate.exists():
            return name, candidate, _parse_peer_file(candidate)
    return PEER_NAME, PEER_FILE, {}


def _detect_ppp_iface() -> str | None:
    """Return the first pppN interface the kernel knows about, if any."""
    net = Path("/sys/class/net")
    if not net.exists():
        return None
    candidates = sorted(p.name for p in net.glob("ppp*"))
    return candidates[0] if candidates else None


async def _ppp_ip(iface: str) -> str | None:
    r = await run_cmd("ip", "-o", "-4", "addr", "show", iface, check=False)
    if r.returncode != 0:
        return None
    m = re.search(r"inet\s+(\S+)", r.stdout)
    return m.group(1).split("/")[0] if m else None


@router.get("/status", response_model=PppoeStatus)
async def status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PppoeStatus:
    if is_mock():
        return PppoeStatus(
            configured=True, active=False, connection_name=PEER_NAME,
            interface=settings.wan_interface, username="user@isp",
        )
    name, _path, parsed = _discover_peer()
    if not parsed:
        return PppoeStatus(configured=False, active=False)
    ppp_iface = _detect_ppp_iface()
    # PPP interfaces report operstate=unknown even when up — so treat "interface
    # exists and has an IPv4 address" as the liveness signal instead.
    ip = await _ppp_ip(ppp_iface) if ppp_iface else None
    return PppoeStatus(
        configured=True,
        active=ip is not None,
        connection_name=name,
        interface=parsed.get("interface"),
        username=parsed.get("username"),
        ip_address=ip,
    )


@router.post("/configure", response_model=OkResponse)
async def configure(
    config: PppoeConfig,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) pppoe configured")
    _validate(config.username, "username")
    iface = config.interface or settings.wan_interface
    _validate(iface, "interface")
    mtu_arg = str(config.mtu) if config.mtu else "-"
    if mtu_arg != "-":
        _validate(mtu_arg, "mtu")
    try:
        # Password goes via stdin so it never hits argv / the process list.
        await run_cmd(
            "sudo", "-n", "/usr/local/sbin/lynkos-pppoe-setup",
            config.username, iface, mtu_arg,
            input_=config.password,
        )
    except NmcliError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e)) from e
    set_pppoe(SavedPppoe(
        username=config.username, password=config.password,
        interface=iface, mtu=config.mtu,
    ))
    return OkResponse(detail="pppoe configured")


@router.post("/up", response_model=OkResponse)
async def up() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) pppoe up")
    name, _path, parsed = _discover_peer()
    if not parsed:
        raise HTTPException(status_code=400, detail="pppoe is not configured")
    try:
        await run_cmd("sudo", "-n", "/usr/bin/pon", name)
    except NmcliError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e)) from e
    return OkResponse(detail="pppoe up")


@router.post("/down", response_model=OkResponse)
async def down() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) pppoe down")
    name, _path, _ = _discover_peer()
    await run_cmd("sudo", "-n", "/usr/bin/poff", name, check=False)
    return OkResponse(detail="pppoe down")


@router.delete("", response_model=OkResponse)
async def remove() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) pppoe removed")
    try:
        await run_cmd("sudo", "-n", "/usr/local/sbin/lynkos-pppoe-remove")
    except NmcliError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e)) from e
    set_pppoe(None)
    return OkResponse(detail="pppoe removed")
