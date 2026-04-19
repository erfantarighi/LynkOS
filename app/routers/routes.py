import ipaddress
import json
import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.models import IpRoute, IpRouteRequest, OkResponse
from app.nm import is_mock, run_cmd
from app.snapshot import SavedRoute, remove_route, upsert_route

router = APIRouter(prefix="/api/routes", tags=["routes"], dependencies=[Depends(current_user)])

_DEV_RE = re.compile(r"^[A-Za-z0-9._:@-]+$")


def _validate_destination(dst: str, family: int) -> None:
    if dst == "default":
        return
    try:
        net = ipaddress.ip_network(dst, strict=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid destination: {e}") from e
    if net.version != family:
        raise HTTPException(status_code=400, detail=f"destination is IPv{net.version}, expected IPv{family}")


def _validate_gateway(gw: str, family: int) -> None:
    try:
        addr = ipaddress.ip_address(gw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid gateway: {e}") from e
    if addr.version != family:
        raise HTTPException(status_code=400, detail=f"gateway is IPv{addr.version}, expected IPv{family}")


def _validate_device(dev: str) -> None:
    if not _DEV_RE.match(dev):
        raise HTTPException(status_code=400, detail="invalid device name")


def _ip_args(req: IpRouteRequest) -> list[str]:
    _validate_destination(req.destination, req.family)
    args = [req.destination]
    if req.gateway:
        _validate_gateway(req.gateway, req.family)
        args += ["via", req.gateway]
    if req.device:
        _validate_device(req.device)
        args += ["dev", req.device]
    if req.metric is not None:
        args += ["metric", str(req.metric)]
    if not req.gateway and not req.device:
        raise HTTPException(status_code=400, detail="gateway or device required")
    return args


@router.get("", response_model=list[IpRoute])
async def list_routes() -> list[IpRoute]:
    if is_mock():
        return [
            IpRoute(family=4, destination="default", gateway="62.155.240.120", device="ppp0"),
            IpRoute(family=4, destination="10.42.0.0/24", device="wlan0", prefsrc="10.42.0.1", metric=600, protocol="kernel", scope="link"),
        ]
    out: list[IpRoute] = []
    for fam in (4, 6):
        r = await run_cmd("ip", "-j", f"-{fam}", "route", "show", check=False)
        if r.returncode != 0 or not r.stdout.strip():
            continue
        try:
            entries = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        for e in entries:
            out.append(
                IpRoute(
                    family=fam,
                    destination=e.get("dst") or "default",
                    gateway=e.get("gateway"),
                    device=e.get("dev"),
                    metric=e.get("metric"),
                    protocol=e.get("protocol"),
                    scope=e.get("scope"),
                    prefsrc=e.get("prefsrc"),
                )
            )
    return out


@router.post("", response_model=OkResponse)
async def add_route(req: IpRouteRequest) -> OkResponse:
    if is_mock():
        return OkResponse(detail=f"(mock) route add {req.destination}")
    args = _ip_args(req)
    r = await run_cmd(
        "sudo", "-n", "/usr/sbin/ip", f"-{req.family}", "route", "add", *args, check=False
    )
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "ip route add failed")
    upsert_route(SavedRoute(
        family=req.family, destination=req.destination,
        gateway=req.gateway, device=req.device, metric=req.metric,
    ))
    return OkResponse(detail="route added")


@router.delete("", response_model=OkResponse)
async def delete_route(req: IpRouteRequest) -> OkResponse:
    if is_mock():
        return OkResponse(detail=f"(mock) route del {req.destination}")
    args = _ip_args(req)
    r = await run_cmd(
        "sudo", "-n", "/usr/sbin/ip", f"-{req.family}", "route", "del", *args, check=False
    )
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "ip route del failed")
    remove_route(SavedRoute(
        family=req.family, destination=req.destination,
        gateway=req.gateway, device=req.device, metric=req.metric,
    ))
    return OkResponse(detail="route deleted")
