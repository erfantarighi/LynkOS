import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends

from app.auth import current_user
from app.models import DhcpLease
from app.nm import is_mock, run_cmd

router = APIRouter(prefix="/api/clients", tags=["clients"], dependencies=[Depends(current_user)])

_MAC_RE = re.compile(r"^[0-9a-fA-F:]{17}$")

# dnsmasq-style lease files we may be able to read. NetworkManager's dir is
# usually root-only, so these often come back empty — ARP is the primary source.
_LEASE_FILES = [Path("/var/lib/misc/dnsmasq.leases")]
_NM_LEASE_DIR = Path("/var/lib/NetworkManager")


def _read_leases() -> dict[str, dict]:
    """Map mac → {hostname, expires} from whichever lease files we can read."""
    leases: dict[str, dict] = {}
    paths = [p for p in _LEASE_FILES if p.is_file()]
    if _NM_LEASE_DIR.is_dir():
        try:
            paths += list(_NM_LEASE_DIR.glob("dnsmasq-*.leases"))
        except PermissionError:
            pass
    for f in paths:
        try:
            text = f.read_text()
        except (OSError, PermissionError):
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                expires, mac, _ip, host = parts[0], parts[1].lower(), parts[2], parts[3]
                if _MAC_RE.match(mac):
                    leases[mac] = {
                        "hostname": host if host != "*" else None,
                        "expires": expires,
                    }
    return leases


async def _read_neighbors() -> list[dict]:
    r = await run_cmd("ip", "-j", "neigh", "show", check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return []


@router.get("", response_model=list[DhcpLease])
async def clients() -> list[DhcpLease]:
    if is_mock():
        return [
            DhcpLease(mac="aa:bb:cc:11:22:33", ip="10.42.0.34", hostname="phone", interface="wlan0", state="REACHABLE"),
            DhcpLease(mac="aa:bb:cc:11:22:44", ip="10.42.0.51", hostname="laptop", interface="wlan0", state="STALE"),
        ]

    lease_meta = _read_leases()
    neighbors = await _read_neighbors()

    results: dict[str, DhcpLease] = {}
    for n in neighbors:
        mac = (n.get("lladdr") or "").lower()
        ip = n.get("dst") or ""
        if not _MAC_RE.match(mac) or not ip or ":" in ip:
            continue
        states = n.get("state") or []
        if "FAILED" in states:
            continue
        state_str = ",".join(states) if states else None
        meta = lease_meta.get(mac, {})
        # If we've seen this MAC already from another iface, keep the first.
        if mac not in results:
            results[mac] = DhcpLease(
                mac=mac,
                ip=ip,
                hostname=meta.get("hostname"),
                expires=meta.get("expires"),
                interface=n.get("dev"),
                state=state_str,
            )

    return sorted(results.values(), key=lambda c: c.ip)
