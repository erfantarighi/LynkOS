import os

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret")

from app.routers.fail2ban import _parse_status  # noqa: E402


SAMPLE = """Status for the jail: lynkos
|- Filter
|  |- Currently failed: 2
|  |- Total failed:     17
|  `- Journal matches:  _SYSTEMD_UNIT=lynkos.service
`- Actions
   |- Currently banned: 1
   |- Total banned:     5
   `- Banned IP list:   203.0.113.42
"""


def test_parse_counts() -> None:
    data = _parse_status(SAMPLE)
    assert data["enabled"] is True
    assert data["currently_failed"] == 2
    assert data["total_failed"] == 17
    assert data["currently_banned"] == 1
    assert data["total_banned"] == 5


def test_parse_banned_ips() -> None:
    data = _parse_status(SAMPLE)
    assert data["banned_ips"] == ["203.0.113.42"]


def test_parse_multiple_banned_ips() -> None:
    text = SAMPLE.replace("203.0.113.42", "203.0.113.42 198.51.100.7 2001:db8::1")
    data = _parse_status(text)
    assert data["banned_ips"] == ["203.0.113.42", "198.51.100.7", "2001:db8::1"]


def test_parse_no_bans() -> None:
    text = SAMPLE.replace("Currently banned: 1", "Currently banned: 0") \
                 .replace("Banned IP list:   203.0.113.42", "Banned IP list:")
    data = _parse_status(text)
    assert data["currently_banned"] == 0
    assert data["banned_ips"] == []
