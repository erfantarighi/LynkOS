from __future__ import annotations

from app.ai.schemas import RouterSecurityState
from app.routers import fail2ban as fail2ban_router
from app.routers import ssh as ssh_router


async def collect_security_state() -> RouterSecurityState:
    ssh = await ssh_router.status()
    fail2ban = await fail2ban_router.status()
    banned_ips: list[str] = []
    failed = 0
    for jail in fail2ban.get("jails", {}).values():
        banned_ips.extend(jail.get("banned_ips", []) or [])
        failed += int(jail.get("currently_failed", 0) or 0)
        failed += int(jail.get("currently_banned", 0) or 0)
    return RouterSecurityState(
        ssh_enabled=bool(ssh.get("enabled") or ssh.get("active")),
        fail2ban_banned_ips=banned_ips,
        recent_failed_logins=failed,
    )
