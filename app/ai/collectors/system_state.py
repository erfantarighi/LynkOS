from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.ai.schemas import (
    MetricsWindowPoint,
    RouterAdblockState,
    RouterDdnsState,
    RouterSnapshotState,
    RouterSpeedtestRun,
    RouterSystemState,
)
from app.config import get_settings
from app.metrics import collector as metrics_collector
from app.routers import adblock as adblock_router
from app.routers import ddns as ddns_router
from app.routers import speedtest as speedtest_router
from app.routers import system as system_router
from app.snapshot import load_snapshot


async def collect_system_state() -> tuple[
    RouterSystemState,
    list[RouterSpeedtestRun],
    RouterDdnsState,
    RouterAdblockState,
    RouterSnapshotState,
    list[MetricsWindowPoint],
]:
    stats = await system_router.stats()
    memory_percent = 0.0
    if stats.memory_total_mb:
        memory_percent = (stats.memory_used_mb / stats.memory_total_mb) * 100

    speedtest_history = await speedtest_router.history()
    ddns = await ddns_router.get_ddns()
    adblock = await adblock_router.status()
    snapshot = load_snapshot()
    metrics_samples = []
    for sample in metrics_collector.snapshot():
        metrics_samples.append(
            MetricsWindowPoint(
                ts=datetime.fromtimestamp(sample["ts"], tz=timezone.utc),
                total_rx_bps=sum(v["rx_bps"] for v in sample["interfaces"].values()),
                total_tx_bps=sum(v["tx_bps"] for v in sample["interfaces"].values()),
            )
        )

    runs = []
    for item in speedtest_history.get("runs", [])[-10:]:
        try:
            runs.append(
                RouterSpeedtestRun(
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    download_mbps=float(item.get("download_mbps", 0)),
                    upload_mbps=float(item.get("upload_mbps", 0)),
                    ping_ms=float(item.get("ping_ms", 0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    last_update = None
    if adblock.get("last_update"):
        try:
            last_update = datetime.fromisoformat(adblock["last_update"])
        except ValueError:
            last_update = None

    settings = get_settings()
    path = (
        Path(settings.snapshot_path)
        if settings.snapshot_path
        else Path(__file__).resolve().parent.parent.parent.parent / "data" / "snapshot.json"
    )
    updated_at = None
    try:
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        updated_at = None

    return (
        RouterSystemState(
            cpu_percent=round(stats.load_avg[0] * 100, 1),
            memory_percent=round(memory_percent, 1),
            temperature_c=stats.cpu_temp_c,
        ),
        runs,
        RouterDdnsState(
            enabled=bool(ddns.get("config", {}).get("enabled")),
            hostnames=list(ddns.get("config", {}).get("hostnames") or []),
            last_ip=ddns.get("config", {}).get("last_ip") or None,
        ),
        RouterAdblockState(
            enabled=bool(adblock.get("enabled")),
            entry_count=int(adblock.get("entry_count", 0)),
            last_update=last_update,
        ),
        RouterSnapshotState(
            has_snapshot=bool(snapshot.routes or snapshot.vlans or snapshot.hotspot or snapshot.pppoe),
            route_count=len(snapshot.routes),
            vlan_count=len(snapshot.vlans),
            updated_at=updated_at,
        ),
        metrics_samples,
    )
