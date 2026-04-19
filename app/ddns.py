"""Dynamic DNS — watches the PPPoE interface's IP and keeps Cloudflare A
records for the configured hostnames pointing at it."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.nm import run_cmd

log = logging.getLogger("lynkos.ddns")

CF_API = "https://api.cloudflare.com/client/v4"


@dataclass
class DdnsState:
    running: bool = False
    zone_id: str | None = None
    current_ip: str | None = None
    last_check_at: str | None = None
    last_update_at: str | None = None
    last_error: str | None = None
    records: list[dict] = field(default_factory=list)  # {hostname, id, content, proxied}


class CloudflareClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=CF_API,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(15.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        r = await self._client.request(method, path, **kwargs)
        try:
            data = r.json()
        except Exception as e:
            raise RuntimeError(f"non-json response from {path}: {e}") from e
        if not r.is_success or not data.get("success"):
            errors = data.get("errors") or [{"message": r.text}]
            raise RuntimeError(f"cloudflare {r.status_code}: {errors[0].get('message')}")
        return data

    async def resolve_zone_id(self, zone: str) -> str:
        data = await self._request("GET", "/zones", params={"name": zone})
        results = data.get("result") or []
        if not results:
            raise RuntimeError(f"zone not found: {zone}")
        return results[0]["id"]

    async def find_a_record(self, zone_id: str, hostname: str) -> dict | None:
        data = await self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"type": "A", "name": hostname},
        )
        results = data.get("result") or []
        return results[0] if results else None

    async def upsert_a_record(
        self, zone_id: str, hostname: str, ip: str, proxied: bool
    ) -> dict:
        existing = await self.find_a_record(zone_id, hostname)
        payload = {
            "type": "A", "name": hostname, "content": ip,
            "ttl": 60, "proxied": proxied,
        }
        if existing:
            if existing.get("content") == ip and existing.get("proxied") == proxied:
                return existing
            data = await self._request(
                "PATCH",
                f"/zones/{zone_id}/dns_records/{existing['id']}",
                json=payload,
            )
        else:
            data = await self._request(
                "POST", f"/zones/{zone_id}/dns_records", json=payload
            )
        return data["result"]


async def current_pppoe_ip() -> str | None:
    net = Path("/sys/class/net")
    if not net.exists():
        return None
    for ppp in sorted(p.name for p in net.glob("ppp*")):
        r = await run_cmd("ip", "-o", "-4", "addr", "show", ppp, check=False)
        if r.returncode != 0:
            continue
        m = re.search(r"inet\s+(\S+)", r.stdout)
        if m:
            return m.group(1).split("/")[0]
    return None


class DdnsRunner:
    """Singleton background task that reconciles DNS records with the current
    PPPoE IP. Restart it after config changes."""

    def __init__(self) -> None:
        self.state = DdnsState()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        await self.stop()
        from app.snapshot import load_snapshot  # avoid import cycle
        snap = load_snapshot()
        if not snap.ddns or not snap.ddns.enabled:
            log.info("ddns disabled — not starting")
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="lynkos.ddns")
        self.state.running = True
        log.info("ddns runner started")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._stop.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        self._task = None
        self.state.running = False

    async def trigger_now(self) -> DdnsState:
        """Run one reconciliation pass synchronously (for the manual button)."""
        await self._reconcile_once()
        return self.state

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                await self._reconcile_once()
                from app.snapshot import load_snapshot
                snap = load_snapshot()
                delay = snap.ddns.interval_seconds if snap.ddns else 60
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=max(delay, 15))
                except asyncio.TimeoutError:
                    continue
        except Exception:
            log.exception("ddns runner crashed")

    async def _reconcile_once(self) -> None:
        from app.snapshot import load_snapshot, save_snapshot
        snap = load_snapshot()
        cfg = snap.ddns
        self.state.last_check_at = datetime.now(timezone.utc).isoformat()
        if not cfg or not cfg.enabled:
            self.state.last_error = "disabled"
            return
        if not cfg.api_token or not cfg.zone or not cfg.hostnames:
            self.state.last_error = "incomplete config"
            return

        ip = await current_pppoe_ip()
        self.state.current_ip = ip
        if not ip:
            self.state.last_error = "no PPPoE IP (ppp* interface has no inet)"
            return

        client = CloudflareClient(cfg.api_token)
        try:
            if not self.state.zone_id:
                self.state.zone_id = await client.resolve_zone_id(cfg.zone)
            updates: list[dict] = []
            for host in cfg.hostnames:
                # "@" is DNS convention for the zone apex.
                if host in ("@", "", cfg.zone):
                    full = cfg.zone
                elif host.endswith(f".{cfg.zone}") or host == cfg.zone:
                    full = host
                else:
                    full = f"{host}.{cfg.zone}"
                rec = await client.upsert_a_record(self.state.zone_id, full, ip, cfg.proxied)
                updates.append({
                    "hostname": full,
                    "id": rec.get("id"),
                    "content": rec.get("content"),
                    "proxied": rec.get("proxied", False),
                })
            self.state.records = updates
            self.state.last_update_at = datetime.now(timezone.utc).isoformat()
            self.state.last_error = None
            # Remember last applied IP in snapshot so the dashboard survives restarts
            snap.ddns.last_ip = ip
            save_snapshot(snap)
        except Exception as e:
            self.state.last_error = str(e)
            log.warning("ddns reconcile failed: %s", e)
        finally:
            await client.aclose()

    def snapshot_state(self) -> dict:
        return asdict(self.state)


runner = DdnsRunner()
