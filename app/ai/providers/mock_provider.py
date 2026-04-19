from __future__ import annotations

import re


class MockAIProvider:
    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        text = user_prompt.strip()
        lowered = text.lower()
        if "wireguard" in lowered and ("peer" in lowered or "vpn" in lowered):
            name_match = re.search(r"\bfor\s+(?:my\s+)?([a-z0-9._-]+)\b", lowered)
            name = (name_match.group(1) if name_match else "new-peer").strip(".,!?")
            platform = "mobile" if any(word in lowered for word in ("iphone", "android", "phone")) else "generic"
            return {
                "intent": "create_wireguard_peer",
                "confidence": 0.95,
                "requires_confirmation": True,
                "risk_level": "medium",
                "explanation": "The request maps to creating a new WireGuard peer.",
                "actions": [
                    {
                        "type": "create_wireguard_peer",
                        "params": {
                            "name": name,
                            "platform": platform,
                            "full_tunnel": True,
                        },
                    }
                ],
                "missing_inputs": [],
            }
        if "disable ssh" in lowered or ("turn off" in lowered and "ssh" in lowered):
            return {
                "intent": "disable_ssh",
                "confidence": 0.97,
                "requires_confirmation": True,
                "risk_level": "medium",
                "explanation": "The request maps to disabling SSH.",
                "actions": [{"type": "disable_ssh", "params": {}}],
                "missing_inputs": [],
            }
        if "enable ssh" in lowered or ("turn on" in lowered and "ssh" in lowered):
            return {
                "intent": "enable_ssh",
                "confidence": 0.97,
                "requires_confirmation": True,
                "risk_level": "medium",
                "explanation": "The request maps to enabling SSH.",
                "actions": [{"type": "enable_ssh", "params": {}}],
                "missing_inputs": [],
            }
        if "enable adblock" in lowered or "turn on adblock" in lowered:
            return {
                "intent": "enable_adblock",
                "confidence": 0.96,
                "requires_confirmation": True,
                "risk_level": "medium",
                "explanation": "The request maps to enabling DNS adblock.",
                "actions": [{"type": "enable_adblock", "params": {}}],
                "missing_inputs": [],
            }
        if "disable adblock" in lowered or "turn off adblock" in lowered:
            return {
                "intent": "disable_adblock",
                "confidence": 0.96,
                "requires_confirmation": True,
                "risk_level": "medium",
                "explanation": "The request maps to disabling DNS adblock.",
                "actions": [{"type": "disable_adblock", "params": {}}],
                "missing_inputs": [],
            }
        if "anomal" in lowered or "suspicious" in lowered:
            return {
                "intent": "explain_anomalies",
                "confidence": 0.78,
                "requires_confirmation": False,
                "risk_level": "low",
                "explanation": "The request asks for an explanation of current anomalies.",
                "actions": [{"type": "explain_anomalies", "params": {}}],
                "missing_inputs": [],
            }
        if "summar" in lowered or "network" in lowered or "internet slow" in lowered:
            return {
                "intent": "summarize_network",
                "confidence": 0.72,
                "requires_confirmation": False,
                "risk_level": "low",
                "explanation": "The request asks for a network summary rather than a configuration change.",
                "actions": [{"type": "summarize_network", "params": {}}],
                "missing_inputs": [],
            }
        return {
            "intent": "unsupported",
            "confidence": 0.32,
            "requires_confirmation": False,
            "risk_level": "low",
            "explanation": "The request does not map cleanly to a supported LynkOS AI action.",
            "actions": [],
            "missing_inputs": [],
        }
