from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]


class RouterSystemState(BaseModel):
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature_c: float | None = None


class RouterInterfaceState(BaseModel):
    name: str
    rx_bps: float = 0.0
    tx_bps: float = 0.0
    ipv4: list[str] = Field(default_factory=list)
    state: str


class RouterClientState(BaseModel):
    mac: str
    ip: str
    hostname: str | None = None
    last_seen: datetime
    is_known: bool = False


class RouterPppoeState(BaseModel):
    connected: bool = False
    interface: str | None = None
    public_ip: str | None = None


class RouterWireGuardPeerState(BaseModel):
    name: str
    latest_handshake: datetime | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0


class RouterWireGuardState(BaseModel):
    enabled: bool = False
    peers: list[RouterWireGuardPeerState] = Field(default_factory=list)


class RouterSecurityState(BaseModel):
    ssh_enabled: bool = False
    fail2ban_banned_ips: list[str] = Field(default_factory=list)
    recent_failed_logins: int = 0


class RouterSpeedtestRun(BaseModel):
    timestamp: datetime
    download_mbps: float
    upload_mbps: float
    ping_ms: float


class RouterDdnsState(BaseModel):
    enabled: bool = False
    hostnames: list[str] = Field(default_factory=list)
    last_ip: str | None = None


class RouterAdblockState(BaseModel):
    enabled: bool = False
    entry_count: int = 0
    last_update: datetime | None = None


class RouterSnapshotState(BaseModel):
    has_snapshot: bool = False
    route_count: int = 0
    vlan_count: int = 0
    updated_at: datetime | None = None


class MetricsWindowPoint(BaseModel):
    ts: datetime
    total_rx_bps: float = 0.0
    total_tx_bps: float = 0.0


class NormalizedRouterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    system: RouterSystemState
    interfaces: list[RouterInterfaceState] = Field(default_factory=list)
    clients: list[RouterClientState] = Field(default_factory=list)
    pppoe: RouterPppoeState = Field(default_factory=RouterPppoeState)
    wireguard: RouterWireGuardState = Field(default_factory=RouterWireGuardState)
    security: RouterSecurityState = Field(default_factory=RouterSecurityState)
    speedtests: list[RouterSpeedtestRun] = Field(default_factory=list)
    ddns: RouterDdnsState = Field(default_factory=RouterDdnsState)
    adblock: RouterAdblockState = Field(default_factory=RouterAdblockState)
    snapshot: RouterSnapshotState = Field(default_factory=RouterSnapshotState)
    metrics_window: list[MetricsWindowPoint] = Field(default_factory=list)


class InsightResponse(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)
    generated_at: datetime


class RecommendationItem(BaseModel):
    id: str
    title: str
    severity: Severity
    reason: str
    recommended_action: str


class RecommendationListResponse(BaseModel):
    items: list[RecommendationItem] = Field(default_factory=list)
    generated_at: datetime


class AnomalyItem(BaseModel):
    id: str
    severity: Severity
    title: str
    explanation: str
    detected_at: datetime


class AnomalyListResponse(BaseModel):
    items: list[AnomalyItem] = Field(default_factory=list)
    generated_at: datetime


class EmptyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateWireGuardPeerParams(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9._-]+$", min_length=1, max_length=32)
    platform: Literal["mobile", "desktop", "generic"] = "generic"
    full_tunnel: bool = True


class CreateWireGuardPeerAction(BaseModel):
    type: Literal["create_wireguard_peer"]
    params: CreateWireGuardPeerParams


class DisableSshAction(BaseModel):
    type: Literal["disable_ssh"]
    params: EmptyParams = Field(default_factory=EmptyParams)


class EnableSshAction(BaseModel):
    type: Literal["enable_ssh"]
    params: EmptyParams = Field(default_factory=EmptyParams)


class EnableAdblockAction(BaseModel):
    type: Literal["enable_adblock"]
    params: EmptyParams = Field(default_factory=EmptyParams)


class DisableAdblockAction(BaseModel):
    type: Literal["disable_adblock"]
    params: EmptyParams = Field(default_factory=EmptyParams)


class SummarizeNetworkAction(BaseModel):
    type: Literal["summarize_network"]
    params: EmptyParams = Field(default_factory=EmptyParams)


class ExplainAnomaliesAction(BaseModel):
    type: Literal["explain_anomalies"]
    params: EmptyParams = Field(default_factory=EmptyParams)


ActionModel = Annotated[
    CreateWireGuardPeerAction
    | DisableSshAction
    | EnableSshAction
    | EnableAdblockAction
    | DisableAdblockAction
    | SummarizeNetworkAction
    | ExplainAnomaliesAction,
    Field(discriminator="type"),
]


class IntentPlan(BaseModel):
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool = True
    risk_level: RiskLevel
    explanation: str
    actions: list[ActionModel] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)


class ParseIntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class IntentReviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    plan: IntentPlan
    approved: bool


class IntentExecuteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    plan: IntentPlan


class IntentExecutionResponse(BaseModel):
    ok: bool = True
    results: list[dict[str, object]] = Field(default_factory=list)
    executed_at: datetime


class AIStatusResponse(BaseModel):
    enabled: bool
    provider: str
    execution_enabled: bool
    available: bool
    reason: str | None = None
