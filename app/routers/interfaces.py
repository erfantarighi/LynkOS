from fastapi import APIRouter, Depends

from app.auth import current_user
from app.models import Interface
from app.nm import is_mock, parse_terse, run

router = APIRouter(prefix="/api/interfaces", tags=["interfaces"], dependencies=[Depends(current_user)])


@router.get("", response_model=list[Interface])
async def list_interfaces() -> list[Interface]:
    if is_mock():
        return [
            Interface(name="eth0", type="ethernet", state="connected", ip_address="192.168.1.10", mac="aa:bb:cc:00:11:22"),
            Interface(name="wlan0", type="wifi", state="connected", ip_address="10.42.0.1", mac="aa:bb:cc:00:11:33"),
        ]
    fields = ["DEVICE", "TYPE", "STATE"]
    dev = await run("-t", "-f", ",".join(fields), "device", "status")
    rows = parse_terse(dev.stdout, ["name", "type", "state"])
    out: list[Interface] = []
    for row in rows:
        name = row["name"]
        if not name or name == "lo":
            continue
        details = await run(
            "-t", "-f", "GENERAL.HWADDR,IP4.ADDRESS", "device", "show", name, check=False
        )
        mac = None
        ip = None
        for line in details.stdout.splitlines():
            if line.startswith("GENERAL.HWADDR:"):
                mac = line.split(":", 1)[1].replace("\\:", ":")
            elif line.startswith("IP4.ADDRESS"):
                val = line.split(":", 1)[1]
                ip = val.split("/")[0] if val else None
        out.append(Interface(name=name, type=row["type"], state=row["state"], ip_address=ip, mac=mac))
    return out
