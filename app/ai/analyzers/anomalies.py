from __future__ import annotations

from app.ai.schemas import AnomalyItem, NormalizedRouterState


def detect_anomalies(state: NormalizedRouterState, known_clients: set[str]) -> tuple[list[AnomalyItem], set[str]]:
    anomalies: list[AnomalyItem] = []
    seen_clients = {client.mac.lower() for client in state.clients}
    now = state.timestamp

    if known_clients:
        for client in state.clients:
            if client.mac.lower() not in known_clients:
                label = client.hostname or client.ip or client.mac
                anomalies.append(
                    AnomalyItem(
                        id=f"new-client-{client.mac.lower()}",
                        severity="medium",
                        title="New client detected",
                        explanation=f"{label} appeared on the network and was not present in the previous AI baseline.",
                        detected_at=now,
                    )
                )

    if len(state.metrics_window) >= 4:
        latest = state.metrics_window[-1]
        previous = state.metrics_window[:-1]
        avg_total = sum(point.total_rx_bps + point.total_tx_bps for point in previous) / len(previous)
        latest_total = latest.total_rx_bps + latest.total_tx_bps
        if avg_total > 0 and latest_total >= max(avg_total * 3, 1_000_000):
            anomalies.append(
                AnomalyItem(
                    id=f"traffic-spike-{int(latest.ts.timestamp())}",
                    severity="medium",
                    title="Bandwidth spike detected",
                    explanation=(
                        f"Current throughput is about {latest_total / 1_000_000:.2f} MB/s, "
                        f"which is well above the recent average of {avg_total / 1_000_000:.2f} MB/s."
                    ),
                    detected_at=latest.ts,
                )
            )
        if latest.total_tx_bps >= max(latest.total_rx_bps * 1.5, 750_000):
            anomalies.append(
                AnomalyItem(
                    id=f"upload-heavy-{int(latest.ts.timestamp())}",
                    severity="medium",
                    title="Upload-heavy traffic observed",
                    explanation="Outbound traffic is significantly higher than inbound traffic right now, which can indicate backup, sync, or unusual client behavior.",
                    detected_at=latest.ts,
                )
            )

    if state.security.recent_failed_logins >= 3 or state.security.fail2ban_banned_ips:
        anomalies.append(
            AnomalyItem(
                id=f"auth-pressure-{int(now.timestamp())}",
                severity="high" if state.security.fail2ban_banned_ips else "medium",
                title="Repeated authentication failures detected",
                explanation="Recent failed logins or banned IPs indicate external login attempts against the router.",
                detected_at=now,
            )
        )

    if state.wireguard.enabled:
        stale = [
            peer.name
            for peer in state.wireguard.peers
            if peer.latest_handshake
            and (now - peer.latest_handshake).total_seconds() > 7 * 24 * 3600
            and (peer.rx_bytes > 0 or peer.tx_bytes > 0)
        ]
        if stale:
            anomalies.append(
                AnomalyItem(
                    id=f"wg-stale-{int(now.timestamp())}",
                    severity="low",
                    title="Inactive WireGuard peers",
                    explanation=f"The following peers have not handshaked in over 7 days: {', '.join(stale)}.",
                    detected_at=now,
                )
            )

    anomalies.sort(key=lambda item: ({"high": 0, "medium": 1, "low": 2}[item.severity], item.id))
    return anomalies, seen_clients
