from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.config import Settings, get_settings
from app.models import HotspotConfig, OkResponse, WifiNetwork
from app.nm import NmcliError, is_mock, parse_terse, run
from app.snapshot import SavedHotspot, set_hotspot

router = APIRouter(prefix="/api/wifi", tags=["wifi"], dependencies=[Depends(current_user)])

HOTSPOT_CONN_NAME = "lynkos-hotspot"


@router.get("/scan", response_model=list[WifiNetwork])
async def scan(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[WifiNetwork]:
    if is_mock():
        return [
            WifiNetwork(ssid="HomeNet", signal=82, security="WPA2", channel=6, in_use=True),
            WifiNetwork(ssid="Neighbor", signal=41, security="WPA2", channel=11),
        ]
    try:
        await run("device", "wifi", "rescan", "ifname", settings.lan_interface, check=False)
    except NmcliError:
        pass
    fields = ["IN-USE", "SSID", "SIGNAL", "SECURITY", "CHAN"]
    result = await run("-t", "-f", ",".join(fields), "device", "wifi", "list")
    rows = parse_terse(result.stdout, [f.lower().replace("-", "_") for f in fields])
    out: list[WifiNetwork] = []
    seen: set[str] = set()
    for row in rows:
        ssid = row.get("ssid") or ""
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(row.get("signal") or 0)
        except ValueError:
            signal = 0
        try:
            channel = int(row["chan"]) if row.get("chan") else None
        except ValueError:
            channel = None
        out.append(
            WifiNetwork(
                ssid=ssid,
                signal=signal,
                security=row.get("security") or "--",
                channel=channel,
                in_use=row.get("in_use") == "*",
            )
        )
    return out


async def _find_ap_connection() -> str | None:
    """Return the name of the first NM wifi connection in AP mode, if any."""
    listing = await run("-t", "-f", "NAME,TYPE", "connection", "show", check=False)
    for line in listing.stdout.splitlines():
        if ":" not in line:
            continue
        name, ctype = line.rsplit(":", 1)
        if ctype != "802-11-wireless":
            continue
        det = await run(
            "-t", "-f", "802-11-wireless.mode", "connection", "show", name, check=False
        )
        for dline in det.stdout.splitlines():
            if dline.startswith("802-11-wireless.mode:") and dline.split(":", 1)[1].strip() == "ap":
                return name
    return None


@router.get("/hotspot")
async def get_hotspot(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    if is_mock():
        return {
            "active": True, "ssid": "LynkOS-AP", "band": "bg", "channel": 6,
            "connection_name": HOTSPOT_CONN_NAME,
        }
    name = await _find_ap_connection()
    if not name:
        return {"active": False, "ssid": None, "band": None, "channel": None, "connection_name": None}
    active_list = await run(
        "-t", "-f", "NAME", "connection", "show", "--active", check=False
    )
    active = any(line == name for line in active_list.stdout.splitlines())
    cfg = await run(
        "-t", "-f",
        "802-11-wireless.ssid,802-11-wireless.band,802-11-wireless.channel",
        "connection", "show", name, check=False,
    )
    values: dict[str, str] = {}
    for line in cfg.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            values[k] = v
    chan = values.get("802-11-wireless.channel") or ""
    return {
        "active": active,
        "ssid": values.get("802-11-wireless.ssid") or None,
        "band": values.get("802-11-wireless.band") or None,
        "channel": int(chan) if chan.isdigit() and int(chan) > 0 else None,
        "connection_name": name,
    }


@router.post("/hotspot", response_model=OkResponse)
async def configure_hotspot(
    config: HotspotConfig,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OkResponse:
    if is_mock():
        return OkResponse(detail=f"(mock) hotspot {config.ssid} configured")
    iface = config.interface or settings.lan_interface
    await run("connection", "delete", HOTSPOT_CONN_NAME, check=False)
    try:
        await run(
            "connection",
            "add",
            "type", "wifi",
            "ifname", iface,
            "con-name", HOTSPOT_CONN_NAME,
            "autoconnect", "yes",
            "ssid", config.ssid,
        )
        await run(
            "connection", "modify", HOTSPOT_CONN_NAME,
            "802-11-wireless.mode", "ap",
            "802-11-wireless.band", config.band,
            "ipv4.method", "shared",
            "ipv6.method", "shared",
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", config.passphrase,
        )
        if config.channel is not None:
            await run(
                "connection", "modify", HOTSPOT_CONN_NAME,
                "802-11-wireless.channel", str(config.channel),
            )
        await run("connection", "up", HOTSPOT_CONN_NAME)
    except NmcliError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    set_hotspot(SavedHotspot(
        ssid=config.ssid, passphrase=config.passphrase,
        band=config.band, channel=config.channel, interface=iface,
    ))
    return OkResponse(detail="hotspot up")


@router.post("/hotspot/stop", response_model=OkResponse)
async def stop_hotspot() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) hotspot stopped")
    # Down whichever AP connection is active, not just ours.
    name = await _find_ap_connection() or HOTSPOT_CONN_NAME
    await run("connection", "down", name, check=False)
    return OkResponse(detail=f"hotspot {name} stopped")
