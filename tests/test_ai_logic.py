import os
import asyncio
from datetime import datetime, timedelta, timezone

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret")

from app.ai.analyzers.anomalies import detect_anomalies
from app.ai.analyzers.intent_parser import parse_intent_plan
from app.ai.analyzers.recommendations import build_recommendations
from app.ai.policies.safety import sanitize_state_for_ai, validate_intent_plan
from app.ai.providers.mock_provider import MockAIProvider
from app.ai.schemas import (
    MetricsWindowPoint,
    NormalizedRouterState,
    RouterAdblockState,
    RouterClientState,
    RouterDdnsState,
    RouterInterfaceState,
    RouterPppoeState,
    RouterSecurityState,
    RouterSnapshotState,
    RouterSystemState,
    RouterWireGuardState,
)


def _state() -> NormalizedRouterState:
    now = datetime.now(timezone.utc)
    return NormalizedRouterState(
        timestamp=now,
        system=RouterSystemState(cpu_percent=22.0, memory_percent=61.0, temperature_c=78.0),
        interfaces=[
            RouterInterfaceState(name="wlan0", rx_bps=100_000, tx_bps=1_500_000, ipv4=["10.42.0.1"], state="connected")
        ],
        clients=[
            RouterClientState(
                mac="aa:bb:cc:dd:ee:ff",
                ip="10.42.0.20",
                hostname="phone",
                last_seen=now,
                is_known=False,
            )
        ],
        pppoe=RouterPppoeState(connected=False, interface="eth0", public_ip="8.8.8.8"),
        wireguard=RouterWireGuardState(enabled=False, peers=[]),
        security=RouterSecurityState(
            ssh_enabled=True,
            fail2ban_banned_ips=["8.8.4.4"],
            recent_failed_logins=4,
        ),
        speedtests=[],
        ddns=RouterDdnsState(enabled=True, hostnames=["home.example.com"], last_ip="8.8.4.4"),
        adblock=RouterAdblockState(enabled=False, entry_count=0, last_update=None),
        snapshot=RouterSnapshotState(has_snapshot=False, route_count=0, vlan_count=0, updated_at=None),
        metrics_window=[
            MetricsWindowPoint(ts=now - timedelta(seconds=8), total_rx_bps=100_000, total_tx_bps=100_000),
            MetricsWindowPoint(ts=now - timedelta(seconds=6), total_rx_bps=120_000, total_tx_bps=110_000),
            MetricsWindowPoint(ts=now - timedelta(seconds=4), total_rx_bps=90_000, total_tx_bps=100_000),
            MetricsWindowPoint(ts=now, total_rx_bps=100_000, total_tx_bps=1_500_000),
        ],
    )


def test_recommendations_include_key_risks() -> None:
    items = build_recommendations(_state())
    ids = {item.id for item in items}
    assert "ssh-exposed" in ids
    assert "wan-disconnected" in ids
    assert "adblock-off" in ids
    assert "high-temp" in ids


def test_anomalies_detect_new_client_and_traffic_spike() -> None:
    anomalies, seen_clients = detect_anomalies(_state(), {"11:22:33:44:55:66"})
    titles = {item.title for item in anomalies}
    assert "New client detected" in titles
    assert "Bandwidth spike detected" in titles
    assert "Upload-heavy traffic observed" in titles
    assert "Repeated authentication failures detected" in titles
    assert "aa:bb:cc:dd:ee:ff" in seen_clients


def test_parse_intent_and_safety_policy() -> None:
    plan = asyncio.run(parse_intent_plan("Create a WireGuard peer for my iPhone", MockAIProvider()))
    safe_plan = validate_intent_plan(plan)
    assert safe_plan.intent == "create_wireguard_peer"
    assert safe_plan.risk_level == "medium"
    assert safe_plan.actions[0].type == "create_wireguard_peer"


def test_sanitizer_masks_public_ips() -> None:
    sanitized = sanitize_state_for_ai(_state())
    assert sanitized.pppoe.public_ip == "8.8.x.x"
    assert sanitized.ddns.last_ip == "8.8.x.x"
    assert sanitized.security.fail2ban_banned_ips == ["8.8.x.x"]
