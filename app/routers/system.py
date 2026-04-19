from pathlib import Path

from fastapi import APIRouter, Depends

from app.auth import current_user
from app.models import SystemStats
from app.nm import is_mock

router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(current_user)])


def _read_cpu_temp() -> float | None:
    for path in (
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ):
        try:
            raw = Path(path).read_text().strip()
            return int(raw) / 1000.0
        except (OSError, ValueError):
            continue
    return None


def _read_meminfo() -> tuple[int, int]:
    total_kb = avail_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total_kb = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail_kb = int(line.split()[1])
    except OSError:
        pass
    total_mb = total_kb // 1024
    used_mb = (total_kb - avail_kb) // 1024
    return total_mb, used_mb


def _read_uptime() -> int:
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError):
        return 0


def _read_loadavg() -> tuple[float, float, float]:
    try:
        parts = Path("/proc/loadavg").read_text().split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (OSError, ValueError, IndexError):
        return (0.0, 0.0, 0.0)


def _read_net_bytes() -> tuple[int, int]:
    rx = tx = 0
    try:
        lines = Path("/proc/net/dev").read_text().splitlines()[2:]
        for line in lines:
            name, _, rest = line.partition(":")
            if name.strip() == "lo":
                continue
            cols = rest.split()
            if len(cols) >= 16:
                rx += int(cols[0])
                tx += int(cols[8])
    except (OSError, ValueError):
        pass
    return rx, tx


@router.get("/stats", response_model=SystemStats)
async def stats() -> SystemStats:
    if is_mock():
        return SystemStats(
            uptime_seconds=12345,
            load_avg=(0.12, 0.08, 0.05),
            cpu_temp_c=48.2,
            memory_total_mb=4096,
            memory_used_mb=812,
            rx_bytes=123_456_789,
            tx_bytes=98_765_432,
        )
    total_mb, used_mb = _read_meminfo()
    rx, tx = _read_net_bytes()
    return SystemStats(
        uptime_seconds=_read_uptime(),
        load_avg=_read_loadavg(),
        cpu_temp_c=_read_cpu_temp(),
        memory_total_mb=total_mb,
        memory_used_mb=used_mb,
        rx_bytes=rx,
        tx_bytes=tx,
    )
