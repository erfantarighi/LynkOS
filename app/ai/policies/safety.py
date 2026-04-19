from __future__ import annotations

import ipaddress

from app.ai.policies.risk_scoring import score_plan_risk
from app.ai.schemas import IntentPlan, NormalizedRouterState

SUPPORTED_ACTIONS = {
    "create_wireguard_peer",
    "disable_ssh",
    "enable_ssh",
    "enable_adblock",
    "disable_adblock",
    "summarize_network",
    "explain_anomalies",
}


def _mask_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.is_private or addr.is_loopback:
        return ip
    if addr.version == 4:
        parts = ip.split(".")
        return ".".join(parts[:2] + ["x", "x"])
    exploded = addr.exploded.split(":")
    return f"{exploded[0]}:{exploded[1]}::"


def sanitize_state_for_ai(state: NormalizedRouterState) -> NormalizedRouterState:
    payload = state.model_dump()
    payload["pppoe"]["public_ip"] = _mask_ip(payload["pppoe"].get("public_ip"))
    payload["security"]["fail2ban_banned_ips"] = [
        _mask_ip(ip) or "redacted" for ip in payload["security"].get("fail2ban_banned_ips", [])
    ]
    payload["ddns"]["last_ip"] = _mask_ip(payload["ddns"].get("last_ip"))
    return NormalizedRouterState.model_validate(payload)


def validate_intent_plan(plan: IntentPlan) -> IntentPlan:
    for action in plan.actions:
        if action.type not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported action type: {action.type}")
    risk = score_plan_risk(plan.actions)
    return plan.model_copy(
        update={
            "risk_level": risk,
            "requires_confirmation": bool(plan.actions),
        }
    )
