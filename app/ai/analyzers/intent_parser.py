from __future__ import annotations

from app.ai.providers.base import AIProvider
from app.ai.schemas import IntentPlan

SYSTEM_PROMPT = """
You are the LynkOS AI intent parser.
Only map requests to these actions:
- create_wireguard_peer
- disable_ssh
- enable_ssh
- enable_adblock
- disable_adblock
- summarize_network
- explain_anomalies

Never invent unsupported actions. If the request is unsupported, return intent=unsupported with no actions.
Always return strict JSON only.
""".strip()


async def parse_intent_plan(text: str, provider: AIProvider | None) -> IntentPlan:
    if provider is None:
        return IntentPlan(
            intent="unsupported",
            confidence=0.0,
            requires_confirmation=False,
            risk_level="low",
            explanation="AI intent parsing is unavailable.",
            actions=[],
            missing_inputs=[],
        )
    raw = await provider.generate_json(SYSTEM_PROMPT, text, IntentPlan.model_json_schema())
    return IntentPlan.model_validate(raw)
