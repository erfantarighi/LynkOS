from __future__ import annotations

from app.ai.schemas import ActionModel, RiskLevel

RISK_BY_ACTION = {
    "create_wireguard_peer": "medium",
    "disable_ssh": "medium",
    "enable_ssh": "medium",
    "enable_adblock": "medium",
    "disable_adblock": "medium",
    "summarize_network": "low",
    "explain_anomalies": "low",
}


def score_plan_risk(actions: list[ActionModel]) -> RiskLevel:
    risk: RiskLevel = "low"
    for action in actions:
        current = RISK_BY_ACTION.get(action.type, "high")
        if current == "high":
            return "high"
        if current == "medium":
            risk = "medium"
    return risk
