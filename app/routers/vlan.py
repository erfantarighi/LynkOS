import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.models import OkResponse, Vlan, VlanRequest
from app.nm import NmcliError, is_mock, run, run_cmd
from app.snapshot import SavedVlan, remove_vlan, upsert_vlan

router = APIRouter(prefix="/api/vlans", tags=["vlans"], dependencies=[Depends(current_user)])

_NAME_RE = re.compile(r"^[A-Za-z0-9._:@-]+$")


def _conn_name(req: VlanRequest) -> str:
    return req.name or f"{req.parent}.{req.vid}"


async def _nm_managed_devices() -> set[str]:
    """Names of devices NetworkManager is actively managing (not `unmanaged`)."""
    r = await run("-t", "-f", "DEVICE,STATE", "device", "status", check=False)
    managed: set[str] = set()
    for line in r.stdout.splitlines():
        if ":" not in line:
            continue
        dev, state = line.split(":", 1)
        if state.strip().lower() != "unmanaged":
            managed.add(dev)
    return managed


def _iface_up(name: str) -> bool:
    op = Path(f"/sys/class/net/{name}/operstate")
    if not op.exists():
        return False
    try:
        state = op.read_text().strip().lower()
    except OSError:
        return False
    # For VLANs "up" or "unknown" (parent carrier gone) both count; only "down" means not up.
    return state != "down"


@router.get("", response_model=list[Vlan])
async def list_vlans() -> list[Vlan]:
    """List VLAN interfaces from the kernel (managed-by-NM or not)."""
    if is_mock():
        return [Vlan(name="eth0.7", parent="eth0", vid=7, active=True, managed=False)]
    r = await run_cmd("ip", "-j", "-d", "link", "show", "type", "vlan", check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        entries = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    managed_devs = await _nm_managed_devices()
    vlans: list[Vlan] = []
    for e in entries:
        name = e.get("ifname") or ""
        linkinfo = e.get("linkinfo") or {}
        info_data = linkinfo.get("info_data") or {}
        vid = info_data.get("id")
        parent = e.get("link") or ""
        if not name or vid is None or not parent:
            continue
        vlans.append(
            Vlan(
                name=name,
                parent=parent,
                vid=int(vid),
                active=_iface_up(name),
                managed=name in managed_devs,
                autoconnect=True,
            )
        )
    return vlans


@router.post("", response_model=OkResponse)
async def create_vlan(req: VlanRequest) -> OkResponse:
    if is_mock():
        return OkResponse(detail=f"(mock) vlan {_conn_name(req)} created")
    name = _conn_name(req)
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid vlan name")
    if req.managed:
        # Remove any existing NM connection with this name, then create a fresh
        # managed one. Auto IP config is a reasonable default; user can tweak
        # afterward with nmcli.
        await run("connection", "delete", name, check=False)
        try:
            await run(
                "connection", "add",
                "type", "vlan", "con-name", name, "ifname", name,
                "dev", req.parent, "id", str(req.vid),
                "ipv4.method", "auto", "ipv6.method", "auto",
                "autoconnect", "yes",
            )
            await run("connection", "up", name)
        except NmcliError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        try:
            await run_cmd(
                "sudo", "-n", "/usr/local/sbin/lynkos-vlan-setup",
                req.parent, str(req.vid), name,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    upsert_vlan(SavedVlan(name=name, parent=req.parent, vid=req.vid, managed=req.managed))
    return OkResponse(detail=f"vlan {name} created ({'managed' if req.managed else 'unmanaged'})")


@router.delete("/{name}", response_model=OkResponse)
async def delete_vlan(name: str) -> OkResponse:
    if is_mock():
        return OkResponse(detail=f"(mock) vlan {name} deleted")
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid vlan name")
    # Best-effort drop of any lingering NM connection with the same name.
    await run("connection", "delete", name, check=False)
    try:
        await run_cmd("sudo", "-n", "/usr/local/sbin/lynkos-vlan-remove", name, check=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    remove_vlan(name)
    return OkResponse(detail=f"vlan {name} deleted")
