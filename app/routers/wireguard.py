import ipaddress
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.models import OkResponse, WgAddPeerRequest, WgSetupRequest
from app.nm import is_mock, run_cmd

router = APIRouter(prefix="/api/wireguard", tags=["wireguard"], dependencies=[Depends(current_user)])

WG_HELPER = "/usr/local/sbin/lynkos-wg"


async def _wg(*args: str) -> str:
    """Run the helper via sudo, return stdout. Raises HTTPException on failure."""
    r = await run_cmd("sudo", "-n", WG_HELPER, *args, check=False)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip() or "wireguard command failed")
    return r.stdout


def _validate_subnet(subnet: str) -> None:
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid subnet: {e}") from e
    if net.version != 4:
        raise HTTPException(status_code=400, detail="only IPv4 subnets are supported")
    if net.num_addresses < 4:
        raise HTTPException(status_code=400, detail="subnet is too small")


@router.get("/status")
async def status() -> dict[str, Any]:
    if is_mock():
        return {
            "initialized": True,
            "meta": {"subnet": "10.7.0.0/24", "port": 51820, "endpoint": "example.com", "server_public": "abc", "server_ip": "10.7.0.1"},
            "running": True,
            "peers": [],
        }
    meta_raw = await _wg("meta")
    meta = json.loads(meta_raw)
    if not meta.get("initialized"):
        return {"initialized": False, "meta": None, "running": False, "peers": []}
    status_raw = await _wg("status")
    status_data = json.loads(status_raw)
    peers_raw = await _wg("list-peers")
    peer_list = json.loads(peers_raw)
    # Merge: name → live stats by public key
    live_by_key = {p["public_key"]: p for p in status_data.get("peers", [])}
    merged = []
    for p in peer_list:
        live = live_by_key.get(p.get("public_key"), {})
        merged.append({
            "name": p.get("name"),
            "public_key": p.get("public_key"),
            "allowed_ips": p.get("allowed_ips"),
            "endpoint": live.get("endpoint"),
            "latest_handshake": live.get("latest_handshake", 0),
            "rx_bytes": live.get("rx_bytes", 0),
            "tx_bytes": live.get("tx_bytes", 0),
        })
    return {
        "initialized": True,
        "meta": meta,
        "running": status_data.get("running", False),
        "peers": merged,
    }


@router.post("/setup", response_model=OkResponse)
async def setup(req: WgSetupRequest) -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) wireguard setup")
    _validate_subnet(req.subnet)
    # Endpoint: restrict to hostnames or IPv4
    if not req.endpoint.replace(".", "").replace("-", "").replace(":", "").isalnum():
        raise HTTPException(status_code=400, detail="invalid endpoint")
    await _wg("setup", req.subnet, str(req.port), req.endpoint)
    return OkResponse(detail="wireguard initialized")


@router.post("/peers")
async def add_peer(req: WgAddPeerRequest) -> dict[str, Any]:
    if is_mock():
        return {"name": req.name, "config": "[Interface]\nPrivateKey = mock\nAddress = 10.7.0.2/32"}
    config_text = await _wg("add-peer", req.name, "yes" if req.full_tunnel else "no")
    return {"name": req.name, "config": config_text}


@router.delete("/peers/{public_key:path}", response_model=OkResponse)
async def delete_peer(public_key: str) -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) peer deleted")
    # Public keys are 44 chars base64; the path converter lets `/` through but this
    # value is handed to a sudoers-narrow helper which validates.
    await _wg("del-peer", public_key)
    return OkResponse(detail="peer deleted")


@router.get("/peers/{name}/config")
async def peer_config(name: str) -> dict[str, Any]:
    if is_mock():
        return {"name": name, "config": "[Interface]\nPrivateKey = mock"}
    config_text = await _wg("peer-config", name)
    return {"name": name, "config": config_text}


@router.post("/teardown", response_model=OkResponse)
async def teardown() -> OkResponse:
    if is_mock():
        return OkResponse(detail="(mock) wireguard torn down")
    await _wg("teardown")
    return OkResponse(detail="wireguard torn down")
