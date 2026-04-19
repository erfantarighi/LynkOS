from __future__ import annotations

from app.ai.schemas import NormalizedRouterState, RecommendationItem


def build_recommendations(state: NormalizedRouterState) -> list[RecommendationItem]:
    items: list[RecommendationItem] = []
    if state.security.ssh_enabled:
        items.append(
            RecommendationItem(
                id="ssh-exposed",
                title="SSH is enabled",
                severity="medium",
                reason="SSH is available on the router. If you do not actively use it, turning it off reduces exposure.",
                recommended_action="Disable SSH unless you need remote shell access.",
            )
        )
    if state.security.recent_failed_logins > 0 or state.security.fail2ban_banned_ips:
        items.append(
            RecommendationItem(
                id="review-exposure",
                title="Recent external login pressure detected",
                severity="medium",
                reason="fail2ban has recent failures or banned IPs, which suggests the router is being probed externally.",
                recommended_action="Review WAN exposure and keep SSH restricted or disabled.",
            )
        )
    if not state.pppoe.connected:
        items.append(
            RecommendationItem(
                id="wan-disconnected",
                title="WAN is not connected",
                severity="high",
                reason="PPPoE is configured but not currently active, so internet access may be degraded or unavailable.",
                recommended_action="Check PPPoE credentials, link state, and upstream VLAN configuration.",
            )
        )
    if state.system.temperature_c is not None and state.system.temperature_c >= 75:
        items.append(
            RecommendationItem(
                id="high-temp",
                title="Router temperature is elevated",
                severity="medium",
                reason="Sustained high temperature on Raspberry Pi hardware can reduce reliability.",
                recommended_action="Improve cooling or reduce sustained load.",
            )
        )
    if state.speedtests:
        latest = state.speedtests[-1]
        if latest.ping_ms >= 80:
            items.append(
                RecommendationItem(
                    id="latency-high",
                    title="Recent latency is elevated",
                    severity="medium",
                    reason=f"The latest speedtest reported {latest.ping_ms:.1f} ms latency.",
                    recommended_action="Check WAN health, DNS, and recent upstream changes.",
                )
            )
    if not state.snapshot.has_snapshot:
        items.append(
            RecommendationItem(
                id="no-snapshot",
                title="No saved snapshot detected",
                severity="low",
                reason="LynkOS can restore saved network state after a restart or misconfiguration, but no snapshot appears to be present.",
                recommended_action="Capture the current live state or export a backup from the dashboard.",
            )
        )
    if not state.adblock.enabled:
        items.append(
            RecommendationItem(
                id="adblock-off",
                title="DNS adblock is disabled",
                severity="low",
                reason="The router is not filtering known ad and tracking domains at the DNS layer.",
                recommended_action="Enable adblock if you want network-wide DNS filtering.",
            )
        )

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda item: (order[item.severity], item.id))
