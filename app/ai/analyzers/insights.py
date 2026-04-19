from __future__ import annotations

from app.ai.schemas import AnomalyItem, NormalizedRouterState, RecommendationItem


def build_insight_summary(
    state: NormalizedRouterState,
    recommendations: list[RecommendationItem],
    anomalies: list[AnomalyItem],
) -> tuple[str, list[str]]:
    highlights: list[str] = []
    device_count = len(state.clients)
    summary_parts = [f"There {'is' if device_count == 1 else 'are'} {device_count} active device{'s' if device_count != 1 else ''} on the network."]

    if state.interfaces:
        top_iface = max(state.interfaces, key=lambda iface: iface.rx_bps + iface.tx_bps)
        total = top_iface.rx_bps + top_iface.tx_bps
        if total > 0:
            line = f"Most current traffic is on {top_iface.name} at about {(total * 8) / 1_000_000:.1f} Mbps."
            highlights.append(line)
            summary_parts.append(line)

    if state.wireguard.enabled:
        if state.wireguard.peers:
            peers = len(state.wireguard.peers)
            summary_parts.append(f"WireGuard is enabled with {peers} peer{'s' if peers != 1 else ''}.")
        else:
            summary_parts.append("WireGuard is enabled but no peers are configured.")

    if state.security.fail2ban_banned_ips:
        count = len(state.security.fail2ban_banned_ips)
        line = f"{count} external IP{'s were' if count != 1 else ' was'} recently blocked by fail2ban."
        highlights.append(line)
        summary_parts.append(line)
    elif state.security.recent_failed_logins:
        summary_parts.append(
            f"{state.security.recent_failed_logins} recent failed login attempts were observed."
        )

    if recommendations:
        highlights.append(recommendations[0].title)
    if anomalies:
        highlights.append(anomalies[0].title)

    return " ".join(summary_parts), highlights[:4]
