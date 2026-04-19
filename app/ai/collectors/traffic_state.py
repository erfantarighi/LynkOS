from __future__ import annotations

from datetime import datetime, timezone

from app.ai.schemas import RouterClientState, RouterInterfaceState
from app.metrics import collector as metrics_collector
from app.routers import clients as clients_router
from app.routers import interfaces as interfaces_router


async def collect_traffic_state(
    known_clients: set[str],
) -> tuple[list[RouterInterfaceState], list[RouterClientState]]:
    interfaces = await interfaces_router.list_interfaces()
    clients = await clients_router.clients()
    samples = metrics_collector.snapshot()
    latest_sample = samples[-1] if samples else None
    rates = latest_sample["interfaces"] if latest_sample else {}

    iface_states = []
    for iface in interfaces:
        rate = rates.get(iface.name, {"rx_bps": 0.0, "tx_bps": 0.0})
        ipv4 = [iface.ip_address] if iface.ip_address else []
        iface_states.append(
            RouterInterfaceState(
                name=iface.name,
                rx_bps=float(rate.get("rx_bps", 0.0)),
                tx_bps=float(rate.get("tx_bps", 0.0)),
                ipv4=ipv4,
                state=iface.state,
            )
        )

    now = datetime.now(timezone.utc)
    client_states = [
        RouterClientState(
            mac=client.mac,
            ip=client.ip,
            hostname=client.hostname,
            last_seen=now,
            is_known=client.mac.lower() in known_clients,
        )
        for client in clients
    ]
    return iface_states, client_states
