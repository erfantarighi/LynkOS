from __future__ import annotations

from datetime import datetime, timezone

from app.ai.schemas import RouterPppoeState, RouterWireGuardPeerState, RouterWireGuardState
from app.config import get_settings
from app.routers import pppoe as pppoe_router
from app.routers import wireguard as wireguard_router


async def collect_wireguard_state() -> tuple[RouterPppoeState, RouterWireGuardState]:
    settings = get_settings()
    pppoe = await pppoe_router.status(settings)
    wg = await wireguard_router.status()

    peers = []
    for peer in wg.get("peers", []):
        handshake = peer.get("latest_handshake") or 0
        peers.append(
            RouterWireGuardPeerState(
                name=peer.get("name") or "peer",
                latest_handshake=(
                    datetime.fromtimestamp(handshake, tz=timezone.utc) if handshake else None
                ),
                rx_bytes=int(peer.get("rx_bytes", 0)),
                tx_bytes=int(peer.get("tx_bytes", 0)),
            )
        )

    return (
        RouterPppoeState(
            connected=bool(pppoe.active),
            interface=pppoe.interface,
            public_ip=pppoe.ip_address,
        ),
        RouterWireGuardState(
            enabled=bool(wg.get("initialized")),
            peers=peers,
        ),
    )
