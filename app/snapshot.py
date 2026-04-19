"""Snapshot of network config so settings that don't persist across reboots
(most notably `ip route` entries) can be re-applied when the service starts.

Design:
- Routers call `upsert_route`/`set_hotspot`/`set_pppoe` after successful config.
- `apply_all()` runs on service startup and is idempotent: every stage checks
  current system state first and skips anything already in place.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.nm import run, run_cmd

log = logging.getLogger("lynkos.snapshot")

SNAPSHOT_VERSION: int = 1
HOTSPOT_CONN_NAME = "lynkos-hotspot"
PPPOE_PEER_NAME = "lynkos-wan"
LEGACY_PPPOE_PEERS = ("dsl-provider", "provider")


@dataclass
class SavedVlan:
    name: str
    parent: str
    vid: int
    # False → raw `ip link` (recommended for PPPoE upstream).
    # True  → NetworkManager connection with ipv4/ipv6 auto (for LAN VLANs).
    managed: bool = False


@dataclass
class SavedRoute:
    family: int
    destination: str
    gateway: str | None = None
    device: str | None = None
    metric: int | None = None


@dataclass
class SavedHotspot:
    ssid: str
    passphrase: str
    band: str = "bg"
    channel: int | None = None
    interface: str | None = None


@dataclass
class SavedAdblock:
    enabled: bool = False
    blocklists: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)
    entry_count: int = 0
    last_update: str = ""
    last_error: str = ""


@dataclass
class SavedDdns:
    enabled: bool = False
    api_token: str = ""
    zone: str = ""
    hostnames: list[str] = field(default_factory=list)
    proxied: bool = False
    interval_seconds: int = 60
    last_ip: str = ""


@dataclass
class SavedPppoe:
    username: str
    # May be empty when captured from an existing peer file (password lives in
    # /etc/ppp/chap-secrets which we don't read). Apply logic uses `pon` in that
    # case and only writes a new peer if both are supplied.
    password: str = ""
    interface: str | None = None
    mtu: int | None = None


@dataclass
class Snapshot:
    version: int = SNAPSHOT_VERSION
    vlans: list[SavedVlan] = field(default_factory=list)
    routes: list[SavedRoute] = field(default_factory=list)
    hotspot: SavedHotspot | None = None
    pppoe: SavedPppoe | None = None
    ddns: SavedDdns | None = None
    adblock: SavedAdblock | None = None

    @classmethod
    def load(cls, path: Path) -> Snapshot:
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            log.warning("snapshot unreadable (%s) — starting fresh", e)
            return cls()
        return cls(
            version=data.get("version", SNAPSHOT_VERSION),
            vlans=[SavedVlan(**v) for v in data.get("vlans", [])],
            routes=[SavedRoute(**r) for r in data.get("routes", [])],
            hotspot=SavedHotspot(**data["hotspot"]) if data.get("hotspot") else None,
            pppoe=SavedPppoe(**data["pppoe"]) if data.get("pppoe") else None,
            ddns=SavedDdns(**data["ddns"]) if data.get("ddns") else None,
            adblock=SavedAdblock(**data["adblock"]) if data.get("adblock") else None,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "vlans": [asdict(v) for v in self.vlans],
            "routes": [asdict(r) for r in self.routes],
            "hotspot": asdict(self.hotspot) if self.hotspot else None,
            "pppoe": asdict(self.pppoe) if self.pppoe else None,
            "ddns": asdict(self.ddns) if self.ddns else None,
            "adblock": asdict(self.adblock) if self.adblock else None,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.chmod(0o600)
        tmp.replace(path)


def _default_path() -> Path:
    cfg = get_settings().snapshot_path
    if cfg:
        return Path(cfg)
    return Path(__file__).resolve().parent.parent / "data" / "snapshot.json"


def load_snapshot() -> Snapshot:
    return Snapshot.load(_default_path())


def save_snapshot(snap: Snapshot) -> None:
    snap.save(_default_path())


def _route_key(r: SavedRoute) -> tuple:
    return (r.family, r.destination, r.gateway, r.device)


def upsert_route(r: SavedRoute) -> None:
    snap = load_snapshot()
    snap.routes = [x for x in snap.routes if _route_key(x) != _route_key(r)]
    snap.routes.append(r)
    save_snapshot(snap)


def remove_route(r: SavedRoute) -> None:
    snap = load_snapshot()
    snap.routes = [x for x in snap.routes if _route_key(x) != _route_key(r)]
    save_snapshot(snap)


def upsert_vlan(v: SavedVlan) -> None:
    snap = load_snapshot()
    snap.vlans = [x for x in snap.vlans if x.name != v.name]
    snap.vlans.append(v)
    save_snapshot(snap)


def remove_vlan(name: str) -> None:
    snap = load_snapshot()
    snap.vlans = [x for x in snap.vlans if x.name != name]
    save_snapshot(snap)


def set_hotspot(h: SavedHotspot | None) -> None:
    snap = load_snapshot()
    snap.hotspot = h
    save_snapshot(snap)


def set_pppoe(p: SavedPppoe | None) -> None:
    snap = load_snapshot()
    snap.pppoe = p
    save_snapshot(snap)


def set_ddns(d: SavedDdns | None) -> None:
    snap = load_snapshot()
    snap.ddns = d
    save_snapshot(snap)


def set_adblock(a: SavedAdblock | None) -> None:
    snap = load_snapshot()
    snap.adblock = a
    save_snapshot(snap)


async def _route_exists(r: SavedRoute) -> bool:
    res = await run_cmd(
        "ip", "-j", f"-{r.family}", "route", "show", r.destination, check=False
    )
    if res.returncode != 0:
        return False
    try:
        entries = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return False
    for e in entries:
        gw_match = not r.gateway or e.get("gateway") == r.gateway
        dev_match = not r.device or e.get("dev") == r.device
        if gw_match and dev_match:
            return True
    return False


async def _apply_route(r: SavedRoute) -> str:
    if await _route_exists(r):
        return "skipped (present)"
    args = [r.destination]
    if r.gateway:
        args += ["via", r.gateway]
    if r.device:
        args += ["dev", r.device]
    if r.metric is not None:
        args += ["metric", str(r.metric)]
    res = await run_cmd(
        "sudo", "-n", "/usr/sbin/ip", f"-{r.family}", "route", "add", *args, check=False
    )
    if res.returncode != 0:
        return f"failed: {res.stderr.strip() or 'unknown'}"
    return "applied"


async def _nm_connection_exists(name: str) -> bool:
    res = await run("-t", "-f", "NAME", "connection", "show", check=False)
    return any(line == name for line in res.stdout.splitlines())


async def _apply_vlan(v: SavedVlan) -> str:
    if v.managed:
        # NM persists its own connections; if it's already there just ensure it's up.
        if await _nm_connection_exists(v.name):
            await run("connection", "up", v.name, check=False)
            return "skipped (managed NM connection exists)"
        try:
            await run(
                "connection", "add",
                "type", "vlan", "con-name", v.name, "ifname", v.name,
                "dev", v.parent, "id", str(v.vid),
                "ipv4.method", "auto", "ipv6.method", "auto",
                "autoconnect", "yes",
            )
            await run("connection", "up", v.name)
        except Exception as e:
            return f"failed: {e}"
        return "applied (managed)"
    # Unmanaged path: helper script is idempotent; removes any NM claim, tells
    # NM to stop managing the device, then `ip link add`s if needed.
    res = await run_cmd(
        "sudo", "-n", "/usr/local/sbin/lynkos-vlan-setup",
        v.parent, str(v.vid), v.name,
        check=False,
    )
    if res.returncode != 0:
        return f"failed: {res.stderr.strip() or 'unknown'}"
    return "ensured up (unmanaged)"


async def _apply_hotspot(h: SavedHotspot) -> str:
    if await _nm_connection_exists(HOTSPOT_CONN_NAME):
        # Already configured — just make sure it's up without reconfiguring.
        await run("connection", "up", HOTSPOT_CONN_NAME, check=False)
        return "skipped (connection exists)"
    iface = h.interface or get_settings().lan_interface
    try:
        await run(
            "connection", "add",
            "type", "wifi", "ifname", iface, "con-name", HOTSPOT_CONN_NAME,
            "autoconnect", "yes", "ssid", h.ssid,
        )
        await run(
            "connection", "modify", HOTSPOT_CONN_NAME,
            "802-11-wireless.mode", "ap",
            "802-11-wireless.band", h.band,
            "ipv4.method", "shared", "ipv6.method", "shared",
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", h.passphrase,
        )
        if h.channel is not None:
            await run(
                "connection", "modify", HOTSPOT_CONN_NAME,
                "802-11-wireless.channel", str(h.channel),
            )
        await run("connection", "up", HOTSPOT_CONN_NAME)
    except Exception as e:
        return f"failed: {e}"
    return "applied"


def _ppp_link_up() -> bool:
    """True if any pppN interface has an IPv4 address — i.e. the link is live."""
    net = Path("/sys/class/net")
    if not net.exists():
        return False
    for ppp in net.glob("ppp*"):
        if ppp.exists():
            return True
    return False


async def _apply_pppoe(p: SavedPppoe) -> str:
    # If a peer file already exists, don't rewrite it — but DO try to dial if the
    # link isn't up. Common case: VLAN just came up and the existing pppoeconf
    # peer is waiting to connect.
    existing_peer: str | None = None
    for name in (PPPOE_PEER_NAME, *LEGACY_PPPOE_PEERS):
        if Path(f"/etc/ppp/peers/{name}").exists():
            existing_peer = name
            break

    if existing_peer:
        if _ppp_link_up():
            return f"skipped ({existing_peer} already up)"
        res = await run_cmd("sudo", "-n", "/usr/bin/pon", existing_peer, check=False)
        if res.returncode != 0:
            return f"pon failed: {res.stderr.strip() or 'unknown'}"
        return f"dialed ({existing_peer})"

    if not p.password:
        return "skipped (no peer file and no saved password)"
    iface = p.interface or get_settings().wan_interface
    mtu_arg = str(p.mtu) if p.mtu else "-"
    res = await run_cmd(
        "sudo", "-n", "/usr/local/sbin/lynkos-pppoe-setup",
        p.username, iface, mtu_arg,
        input_=p.password, check=False,
    )
    if res.returncode != 0:
        return f"setup failed: {res.stderr.strip() or 'unknown'}"
    # Bring it up right after writing config.
    up = await run_cmd("sudo", "-n", "/usr/bin/pon", PPPOE_PEER_NAME, check=False)
    if up.returncode != 0:
        return f"configured but pon failed: {up.stderr.strip() or 'unknown'}"
    return "applied and dialed"


async def _nmcli_show(name: str, fields: list[str], secrets: bool = False) -> dict[str, str]:
    args = ["-t"]
    if secrets:
        args.append("-s")
    args += ["-f", ",".join(fields), "connection", "show", name]
    # sudo only needed when secrets are requested; plain show works unprivileged.
    if secrets:
        res = await run_cmd("sudo", "-n", "/usr/bin/nmcli", *args, check=False)
    else:
        res = await run(*args, check=False)
    out: dict[str, str] = {}
    for line in res.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


async def capture_live() -> dict[str, Any]:
    """Populate the snapshot from what's currently running on the system."""
    import re as _re
    snap = load_snapshot()
    captured: dict[str, Any] = {"vlans": 0, "routes": 0, "hotspot": False, "pppoe": False}

    # --- VLANs (read from the kernel: covers NM-managed and raw `ip link` VLANs) ---
    new_vlans: list[SavedVlan] = []
    r = await run_cmd("ip", "-j", "-d", "link", "show", "type", "vlan", check=False)
    if r.returncode == 0 and r.stdout.strip():
        try:
            entries = json.loads(r.stdout)
        except json.JSONDecodeError:
            entries = []
        # Determine NM-managed-ness per device.
        dev_status = await run("-t", "-f", "DEVICE,STATE", "device", "status", check=False)
        unmanaged: set[str] = set()
        for line in dev_status.stdout.splitlines():
            if ":" in line:
                dev, state = line.split(":", 1)
                if state.strip().lower() == "unmanaged":
                    unmanaged.add(dev)
        for e in entries:
            name = e.get("ifname") or ""
            parent = e.get("link") or ""
            vid = (e.get("linkinfo") or {}).get("info_data", {}).get("id")
            if name and parent and vid is not None:
                new_vlans.append(SavedVlan(
                    name=name, parent=parent, vid=int(vid),
                    managed=name not in unmanaged,
                ))
    if new_vlans:
        snap.vlans = new_vlans
        captured["vlans"] = len(new_vlans)

    # --- Routes ---
    # Capture everything visible. The applier checks existence first, so
    # kernel-managed routes (which the OS will recreate on boot) are skipped
    # silently and only genuinely-missing ones are re-added.
    # Skip IPv6 link-local (fe80::/64 etc.) — those are auto-generated per-iface.
    new_routes: list[SavedRoute] = []
    for fam in (4, 6):
        r = await run_cmd("ip", "-j", f"-{fam}", "route", "show", check=False)
        if r.returncode != 0:
            continue
        try:
            entries = json.loads(r.stdout or "[]")
        except json.JSONDecodeError:
            continue
        for e in entries:
            dst = e.get("dst") or "default"
            if fam == 6 and dst.startswith("fe80"):
                continue
            new_routes.append(SavedRoute(
                family=fam,
                destination=dst,
                gateway=e.get("gateway"),
                device=e.get("dev"),
                metric=e.get("metric"),
            ))
    snap.routes = new_routes
    captured["routes"] = len(new_routes)

    # --- Hotspot (first wifi-AP connection found; uses `nmcli -s` for PSK) ---
    res = await run("-t", "-f", "NAME,TYPE", "connection", "show", check=False)
    for line in res.stdout.splitlines():
        if not line or ":" not in line:
            continue
        name, ctype = line.rsplit(":", 1)
        if ctype != "802-11-wireless":
            continue
        d = await _nmcli_show(
            name,
            [
                "802-11-wireless.mode", "802-11-wireless.ssid",
                "802-11-wireless.band", "802-11-wireless.channel",
                "802-11-wireless-security.psk", "connection.interface-name",
            ],
            secrets=True,
        )
        if d.get("802-11-wireless.mode") != "ap":
            continue
        ssid = d.get("802-11-wireless.ssid", "")
        if not ssid:
            continue
        chan_raw = d.get("802-11-wireless.channel", "")
        snap.hotspot = SavedHotspot(
            ssid=ssid,
            passphrase=d.get("802-11-wireless-security.psk", ""),
            band=d.get("802-11-wireless.band", "") or "bg",
            channel=int(chan_raw) if chan_raw.isdigit() and int(chan_raw) > 0 else None,
            interface=d.get("connection.interface-name") or None,
        )
        captured["hotspot"] = True
        break

    # --- PPPoE (from whichever peer file exists; password not captured) ---
    for name in (PPPOE_PEER_NAME, *LEGACY_PPPOE_PEERS):
        peer = Path(f"/etc/ppp/peers/{name}")
        if not peer.exists():
            continue
        try:
            text = peer.read_text()
        except (OSError, PermissionError):
            continue
        iface: str | None = None
        user: str | None = None
        mtu: int | None = None
        for raw in text.splitlines():
            s = raw.strip()
            if s.startswith("plugin rp-pppoe.so"):
                parts = s.split()
                if len(parts) >= 3:
                    iface = parts[2]
            elif s.startswith("user "):
                m = _re.match(r'user\s+"?([^"\s]+)"?', s)
                if m:
                    user = m.group(1)
            elif s.startswith("mtu "):
                parts = s.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    mtu = int(parts[1])
        if user:
            # Keep any previously saved password (e.g. configured via UI earlier)
            prev_pw = snap.pppoe.password if snap.pppoe and snap.pppoe.username == user else ""
            snap.pppoe = SavedPppoe(username=user, password=prev_pw, interface=iface, mtu=mtu)
            captured["pppoe"] = True
            break

    save_snapshot(snap)
    return captured


async def apply_all() -> dict[str, Any]:
    """Re-apply snapshot to live system, skipping anything already set up.

    Order matters: VLANs first (PPPoE may depend on eth0.X), then routes,
    then hotspot, then PPPoE.
    """
    snap = load_snapshot()
    results: dict[str, Any] = {"vlans": [], "routes": [], "hotspot": None, "pppoe": None}

    for v in snap.vlans:
        outcome = await _apply_vlan(v)
        log.info("vlan %s (parent=%s vid=%d) → %s", v.name, v.parent, v.vid, outcome)
        results["vlans"].append({"vlan": asdict(v), "result": outcome})

    for r in snap.routes:
        outcome = await _apply_route(r)
        log.info("route %s %s → %s", r.destination, r.device or r.gateway or "", outcome)
        results["routes"].append({"route": asdict(r), "result": outcome})

    if snap.hotspot:
        results["hotspot"] = await _apply_hotspot(snap.hotspot)
        log.info("hotspot %s → %s", snap.hotspot.ssid, results["hotspot"])

    if snap.pppoe:
        results["pppoe"] = await _apply_pppoe(snap.pppoe)
        log.info("pppoe %s → %s", snap.pppoe.username, results["pppoe"])

    return results
