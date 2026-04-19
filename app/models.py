from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class WifiNetwork(BaseModel):
    ssid: str
    signal: int
    security: str
    channel: int | None = None
    in_use: bool = False


class HotspotConfig(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    passphrase: str = Field(min_length=8, max_length=63)
    band: str = Field(default="bg", pattern="^(a|bg)$")
    channel: int | None = None
    interface: str | None = None


class PppoeConfig(BaseModel):
    username: str
    password: str
    interface: str | None = None
    mtu: int | None = Field(default=None, ge=576, le=1500)
    connection_name: str = "pppoe-wan"


class PppoeStatus(BaseModel):
    configured: bool
    active: bool
    connection_name: str | None = None
    interface: str | None = None
    username: str | None = None
    ip_address: str | None = None


class Interface(BaseModel):
    name: str
    type: str
    state: str
    ip_address: str | None = None
    mac: str | None = None


class DhcpLease(BaseModel):
    mac: str
    ip: str
    hostname: str | None = None
    expires: str | None = None
    interface: str | None = None
    state: str | None = None


class SystemStats(BaseModel):
    uptime_seconds: int
    load_avg: tuple[float, float, float]
    cpu_temp_c: float | None = None
    memory_total_mb: int
    memory_used_mb: int
    rx_bytes: int
    tx_bytes: int


class WgSetupRequest(BaseModel):
    subnet: str = Field(default="10.7.0.0/24")
    port: int = Field(default=51820, ge=1, le=65535)
    endpoint: str = Field(min_length=1, max_length=253)


class WgAddPeerRequest(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9._-]+$", min_length=1, max_length=32)
    full_tunnel: bool = True


class AdblockConfig(BaseModel):
    enabled: bool = False
    blocklists: list[str] = Field(default_factory=list)
    allowlist: list[str] = Field(default_factory=list)


class DdnsConfig(BaseModel):
    enabled: bool = False
    api_token: str = ""
    zone: str = ""
    hostnames: list[str] = Field(default_factory=list)
    proxied: bool = False
    interval_seconds: int = Field(default=60, ge=15, le=3600)


class OkResponse(BaseModel):
    ok: bool = True
    detail: str | None = None


class Vlan(BaseModel):
    name: str
    parent: str
    vid: int
    active: bool = False
    managed: bool = False
    autoconnect: bool = True


class VlanRequest(BaseModel):
    parent: str = Field(pattern=r"^[A-Za-z0-9._:@-]+$", max_length=15)
    vid: int = Field(ge=1, le=4094)
    name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:@-]+$", max_length=15)
    managed: bool = False


class IpRoute(BaseModel):
    family: int
    destination: str
    gateway: str | None = None
    device: str | None = None
    metric: int | None = None
    protocol: str | None = None
    scope: str | None = None
    prefsrc: str | None = None


class IpRouteRequest(BaseModel):
    family: int = Field(default=4, ge=4, le=6)
    destination: str = Field(min_length=1, max_length=64)
    gateway: str | None = None
    device: str | None = Field(default=None, max_length=15)
    metric: int | None = Field(default=None, ge=0, le=2**31 - 1)
