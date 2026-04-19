import os
from pathlib import Path

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret")

from app.snapshot import (  # noqa: E402
    SavedAdblock,
    SavedDdns,
    SavedHotspot,
    SavedPppoe,
    SavedRoute,
    SavedVlan,
    Snapshot,
)


def test_roundtrip_empty(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    Snapshot().save(path)
    loaded = Snapshot.load(path)
    assert loaded.vlans == []
    assert loaded.routes == []
    assert loaded.hotspot is None
    assert loaded.pppoe is None
    assert loaded.ddns is None
    assert loaded.adblock is None


def test_roundtrip_full(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    s = Snapshot(
        vlans=[SavedVlan(name="eth0.7", parent="eth0", vid=7, managed=False)],
        routes=[
            SavedRoute(family=4, destination="default", gateway=None, device="ppp0"),
            SavedRoute(family=4, destination="10.0.0.0/24", gateway="10.0.0.1", device="eth0", metric=100),
        ],
        hotspot=SavedHotspot(ssid="Home", passphrase="hunter22", band="bg", channel=6),
        pppoe=SavedPppoe(username="user@isp", password="p@ss", interface="eth0.7", mtu=1492),
        ddns=SavedDdns(enabled=True, api_token="tok", zone="example.com", hostnames=["@"]),
        adblock=SavedAdblock(enabled=True, blocklists=["https://x"], allowlist=["y.com"]),
    )
    s.save(path)
    loaded = Snapshot.load(path)
    assert loaded.vlans[0].name == "eth0.7" and loaded.vlans[0].vid == 7
    assert loaded.vlans[0].managed is False
    assert len(loaded.routes) == 2
    assert loaded.routes[1].metric == 100
    assert loaded.hotspot.ssid == "Home"
    assert loaded.pppoe.username == "user@isp"
    assert loaded.ddns.enabled is True and loaded.ddns.hostnames == ["@"]
    assert loaded.adblock.enabled is True


def test_file_mode_is_0600(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    Snapshot(hotspot=SavedHotspot(ssid="x", passphrase="y"*8)).save(path)
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_corrupt_file_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text("{not valid json")
    loaded = Snapshot.load(path)
    assert loaded.vlans == [] and loaded.routes == []


def test_backwards_compat_missing_fields(tmp_path: Path) -> None:
    # A snapshot from an older version (before adblock existed) still loads.
    path = tmp_path / "snapshot.json"
    path.write_text('{"version": 1, "vlans": [], "routes": []}')
    loaded = Snapshot.load(path)
    assert loaded.adblock is None
    assert loaded.ddns is None
