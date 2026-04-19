"""DNS-level adblock. Downloads hosts-style blocklists, merges them with any
user allowlist, writes a single hosts file that NetworkManager's dnsmasq
points at via /etc/NetworkManager/dnsmasq-shared.d/lynkos-adblock.conf."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.nm import run_cmd

log = logging.getLogger("lynkos.adblock")

HOSTS_DIR = Path("/var/lib/lynkos/adblock")
HOSTS_FILE = HOSTS_DIR / "hosts"

DEFAULT_BLOCKLISTS = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
]

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:(?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63}$"
)
_IGNORE = {"localhost", "localhost.localdomain", "broadcasthost", "local", "ip6-localhost"}

_update_lock = asyncio.Lock()


async def _fetch(url: str, client: httpx.AsyncClient) -> str:
    r = await client.get(url)
    r.raise_for_status()
    return r.text


def _parse_lines(text: str) -> set[str]:
    domains: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("0.0.0.0", "127.0.0.1", "::1", "::"):
            d = parts[1]
        elif len(parts) == 1:
            d = parts[0]
        else:
            continue
        d = d.lower()
        if d in _IGNORE:
            continue
        if _DOMAIN_RE.match(d):
            domains.add(d)
    return domains


async def fetch_all(urls: list[str]) -> tuple[set[str], list[str]]:
    """Return (domains, failed_urls)."""
    all_domains: set[str] = set()
    failed: list[str] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for url in urls:
            try:
                text = await _fetch(url, client)
                all_domains |= _parse_lines(text)
            except Exception as e:
                log.warning("blocklist fetch failed: %s → %s", url, e)
                failed.append(f"{url}: {e}")
    return all_domains, failed


def write_hosts(domains: set[str], allowlist: set[str]) -> int:
    HOSTS_DIR.mkdir(parents=True, exist_ok=True)
    filtered = sorted(d for d in domains if d not in allowlist)
    tmp = HOSTS_FILE.with_suffix(".tmp")
    with tmp.open("w") as f:
        f.write("# Managed by LynkOS adblock — do not edit by hand\n")
        for d in filtered:
            f.write(f"0.0.0.0 {d}\n")
    tmp.replace(HOSTS_FILE)
    return len(filtered)


async def update(
    blocklists: list[str], allowlist: list[str]
) -> tuple[int, list[str], str]:
    """Download all blocklists, write the merged hosts file, SIGHUP dnsmasq.
    Returns (entries_written, failed_urls, timestamp)."""
    async with _update_lock:
        domains, failed = await fetch_all(blocklists)
        if not domains and failed:
            raise RuntimeError("all blocklists failed to download")
        count = write_hosts(domains, set(a.lower() for a in allowlist if a))
        await run_cmd("sudo", "-n", "/usr/local/sbin/lynkos-adblock", "reload", check=False)
        return count, failed, datetime.now(timezone.utc).isoformat()


async def enable_on_hotspot() -> None:
    """Install the NM drop-in and bounce the hotspot so dnsmasq relaunches."""
    r = await run_cmd("sudo", "-n", "/usr/local/sbin/lynkos-adblock", "install", check=False)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "adblock install failed")


async def disable_on_hotspot() -> None:
    r = await run_cmd("sudo", "-n", "/usr/local/sbin/lynkos-adblock", "uninstall", check=False)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "adblock uninstall failed")


def current_entry_count() -> int:
    if not HOSTS_FILE.exists():
        return 0
    try:
        return sum(1 for ln in HOSTS_FILE.read_text().splitlines()
                   if ln and not ln.startswith("#"))
    except OSError:
        return 0
