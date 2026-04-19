"""Lightweight in-memory metrics collector — samples CPU / memory / per-interface
throughput every couple of seconds and keeps a rolling window for the Dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger("lynkos.metrics")

SAMPLE_INTERVAL = 2.0  # seconds between samples
WINDOW_SECONDS = 300   # keep ~5 minutes
MAX_POINTS = int(WINDOW_SECONDS / SAMPLE_INTERVAL)


@dataclass
class IfaceRate:
    rx_bps: float = 0.0
    tx_bps: float = 0.0


@dataclass
class Sample:
    ts: float
    cpu_pct: float
    mem_used_mb: int
    mem_total_mb: int
    cpu_temp_c: float | None
    interfaces: dict[str, IfaceRate] = field(default_factory=dict)


def _read_cpu() -> tuple[int, int]:
    """Return (idle_ticks, total_ticks) from /proc/stat aggregate CPU line."""
    try:
        line = Path("/proc/stat").read_text().splitlines()[0]
        parts = [int(x) for x in line.split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0)  # idle + iowait
        return idle, sum(parts)
    except (OSError, ValueError, IndexError):
        return 0, 0


def _read_net() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    try:
        lines = Path("/proc/net/dev").read_text().splitlines()[2:]
    except OSError:
        return out
    for line in lines:
        name, _, rest = line.partition(":")
        name = name.strip()
        if not name or name == "lo":
            continue
        cols = rest.split()
        if len(cols) >= 16:
            try:
                out[name] = (int(cols[0]), int(cols[8]))
            except ValueError:
                continue
    return out


def _read_mem() -> tuple[int, int]:
    total_kb = avail_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail_kb = int(line.split()[1])
    except (OSError, ValueError):
        pass
    total_mb = total_kb // 1024
    used_mb = (total_kb - avail_kb) // 1024
    return total_mb, used_mb


def _read_temp() -> float | None:
    for path in (
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ):
        try:
            return int(Path(path).read_text().strip()) / 1000.0
        except (OSError, ValueError):
            continue
    return None


class MetricsCollector:
    def __init__(self) -> None:
        self._buf: deque[Sample] = deque(maxlen=MAX_POINTS)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._prev_cpu: tuple[int, int] | None = None
        self._prev_net: dict[str, tuple[float, int, int]] = {}

    async def start(self) -> None:
        await self.stop()
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._loop(), name="lynkos.metrics")
        log.info("metrics collector started (interval=%ss, window=%ss)",
                 SAMPLE_INTERVAL, WINDOW_SECONDS)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._stop.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        self._task = None

    def snapshot(self) -> list[dict]:
        out: list[dict] = []
        for s in self._buf:
            d = asdict(s)
            # asdict on nested dataclasses handles conversion already
            out.append(d)
        return out

    async def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    s = self._collect()
                    if s is not None:
                        self._buf.append(s)
                except Exception:
                    log.exception("metrics sample failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=SAMPLE_INTERVAL)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass

    def _collect(self) -> Sample | None:
        now = time.time()
        cur_cpu = _read_cpu()
        cpu_pct = 0.0
        if self._prev_cpu and cur_cpu[1] > self._prev_cpu[1]:
            d_idle = cur_cpu[0] - self._prev_cpu[0]
            d_total = cur_cpu[1] - self._prev_cpu[1]
            if d_total > 0:
                cpu_pct = max(0.0, min(100.0, 100.0 * (1.0 - d_idle / d_total)))
        self._prev_cpu = cur_cpu

        cur_net = _read_net()
        ifaces: dict[str, IfaceRate] = {}
        for name, (rx, tx) in cur_net.items():
            prev = self._prev_net.get(name)
            self._prev_net[name] = (now, rx, tx)
            if prev:
                dt = now - prev[0]
                if dt > 0:
                    ifaces[name] = IfaceRate(
                        rx_bps=max(0.0, (rx - prev[1]) / dt),
                        tx_bps=max(0.0, (tx - prev[2]) / dt),
                    )

        mem_total, mem_used = _read_mem()
        return Sample(
            ts=now,
            cpu_pct=round(cpu_pct, 1),
            mem_used_mb=mem_used,
            mem_total_mb=mem_total,
            cpu_temp_c=_read_temp(),
            interfaces=ifaces,
        )


collector = MetricsCollector()
