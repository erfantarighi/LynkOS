from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.ai.analyzers import (
    build_insight_summary,
    build_recommendations,
    detect_anomalies,
    parse_intent_plan,
)
from app.ai.collectors import (
    collect_security_state,
    collect_system_state,
    collect_traffic_state,
    collect_wireguard_state,
)
from app.ai.history import AIHistoryStore
from app.ai.policies import sanitize_state_for_ai, validate_intent_plan
from app.ai.providers import MockAIProvider, OpenAIProvider
from app.ai.providers.base import AIProvider
from app.ai.schemas import (
    AIStatusResponse,
    AnomalyListResponse,
    InsightResponse,
    IntentExecuteRequest,
    IntentExecutionResponse,
    IntentPlan,
    NormalizedRouterState,
    RecommendationListResponse,
)
from app.config import get_settings
from app.models import WgAddPeerRequest
from app.routers import adblock as adblock_router
from app.routers import ssh as ssh_router
from app.routers import wireguard as wireguard_router


class AIService:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parent.parent.parent / "data"
        self._history = AIHistoryStore(root)
        self._cache_lock = asyncio.Lock()
        self._cached_state: NormalizedRouterState | None = None
        self._cached_at: float = 0.0
        self._provider: AIProvider | None = None

    def _get_provider(self) -> AIProvider | None:
        settings = get_settings()
        if settings.ai_provider == "mock":
            if not isinstance(self._provider, MockAIProvider):
                self._provider = MockAIProvider()
            return self._provider
        if settings.ai_provider == "openai":
            if not isinstance(self._provider, OpenAIProvider):
                self._provider = OpenAIProvider(
                    api_key=settings.ai_api_key,
                    model=settings.ai_model,
                )
            return self._provider
        return None

    def status(self) -> AIStatusResponse:
        settings = get_settings()
        provider = self._get_provider() if settings.ai_enabled else None
        available = bool(provider) if settings.ai_enabled else False
        reason = None
        if not settings.ai_enabled:
            reason = "AI features are disabled by configuration."
        elif provider is None:
            reason = f"Unsupported provider: {settings.ai_provider}"
        elif settings.ai_provider == "openai" and not settings.ai_api_key:
            available = False
            reason = "LYNKOS_AI_API_KEY is missing."
        return AIStatusResponse(
            enabled=settings.ai_enabled,
            provider=settings.ai_provider,
            execution_enabled=settings.ai_allow_action_execution,
            available=available,
            reason=reason,
        )

    def _require_enabled(self) -> None:
        status = self.status()
        if not status.enabled:
            raise HTTPException(status_code=503, detail=status.reason or "AI disabled")

    async def collect_state(self, force: bool = False) -> NormalizedRouterState:
        self._require_enabled()
        settings = get_settings()
        async with self._cache_lock:
            now = time.monotonic()
            if (
                not force
                and self._cached_state is not None
                and (now - self._cached_at) < settings.ai_state_cache_seconds
            ):
                return self._cached_state

            known_clients = self._history.get_known_clients()
            system, speedtests, ddns, adblock, snapshot, metrics_window = await collect_system_state()
            interfaces, clients = await collect_traffic_state(known_clients)
            security = await collect_security_state()
            pppoe, wireguard = await collect_wireguard_state()

            state = NormalizedRouterState(
                timestamp=datetime.now(timezone.utc),
                system=system,
                interfaces=interfaces,
                clients=clients,
                pppoe=pppoe,
                wireguard=wireguard,
                security=security,
                speedtests=speedtests,
                ddns=ddns,
                adblock=adblock,
                snapshot=snapshot,
                metrics_window=metrics_window,
            )
            self._cached_state = state
            self._cached_at = now
            return state

    async def insights(self) -> InsightResponse:
        state = sanitize_state_for_ai(await self.collect_state())
        recommendations = build_recommendations(state)
        anomalies, seen_clients = detect_anomalies(state, self._history.get_known_clients())
        summary, highlights = build_insight_summary(state, recommendations, anomalies)
        self._history.remember_clients(seen_clients)
        response = InsightResponse(
            summary=summary,
            highlights=highlights,
            generated_at=datetime.now(timezone.utc),
        )
        self._history.append_history("insights", response.model_dump(mode="json"))
        return response

    async def recommendations(self) -> RecommendationListResponse:
        state = sanitize_state_for_ai(await self.collect_state())
        response = RecommendationListResponse(
            items=build_recommendations(state),
            generated_at=datetime.now(timezone.utc),
        )
        self._history.append_history("recommendations", response.model_dump(mode="json"))
        return response

    async def anomalies(self) -> AnomalyListResponse:
        state = sanitize_state_for_ai(await self.collect_state())
        anomalies, seen_clients = detect_anomalies(state, self._history.get_known_clients())
        self._history.remember_clients(seen_clients)
        response = AnomalyListResponse(items=anomalies, generated_at=datetime.now(timezone.utc))
        self._history.append_history("anomalies", response.model_dump(mode="json"))
        return response

    async def parse_intent(self, username: str, text: str) -> IntentPlan:
        self._require_enabled()
        plan = validate_intent_plan(await parse_intent_plan(text, self._get_provider()))
        self._history.append_audit(
            {
                "username": username,
                "event": "parsed",
                "prompt_text": text,
                "plan": plan.model_dump(mode="json"),
                "confidence": plan.confidence,
                "risk_level": plan.risk_level,
            }
        )
        self._history.append_history(
            "parsed_intents",
            {"prompt_text": text, "plan": plan.model_dump(mode="json")},
        )
        return plan

    async def review_intent(self, username: str, text: str, plan: IntentPlan, approved: bool) -> None:
        safe_plan = validate_intent_plan(plan)
        self._history.append_audit(
            {
                "username": username,
                "event": "approved" if approved else "rejected",
                "prompt_text": text,
                "plan": safe_plan.model_dump(mode="json"),
                "confidence": safe_plan.confidence,
                "risk_level": safe_plan.risk_level,
            }
        )

    async def execute_intent(self, username: str, request: IntentExecuteRequest) -> IntentExecutionResponse:
        self._require_enabled()
        settings = get_settings()
        if not settings.ai_allow_action_execution:
            raise HTTPException(status_code=403, detail="AI action execution is disabled")
        plan = validate_intent_plan(request.plan)
        results: list[dict[str, Any]] = []
        for action in plan.actions:
            if action.type == "create_wireguard_peer":
                result = await wireguard_router.add_peer(
                    WgAddPeerRequest(
                        name=action.params.name,
                        full_tunnel=action.params.full_tunnel,
                    )
                )
            elif action.type == "disable_ssh":
                result = await ssh_router.disable()
            elif action.type == "enable_ssh":
                result = await ssh_router.enable()
            elif action.type == "enable_adblock":
                result = (await adblock_router.enable()).model_dump(mode="json")
            elif action.type == "disable_adblock":
                result = (await adblock_router.disable()).model_dump(mode="json")
            else:
                result = {"detail": "no execution needed"}
            results.append({"type": action.type, "result": result})

        executed_at = datetime.now(timezone.utc)
        self._history.append_audit(
            {
                "username": username,
                "event": "executed",
                "prompt_text": request.text,
                "plan": plan.model_dump(mode="json"),
                "confidence": plan.confidence,
                "risk_level": plan.risk_level,
                "execution_result": results,
            }
        )
        self._history.append_history(
            "execution_results",
            {"prompt_text": request.text, "results": results},
        )
        return IntentExecutionResponse(ok=True, results=results, executed_at=executed_at)


service = AIService()
