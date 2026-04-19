import os

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.models import IpRouteRequest  # noqa: E402
from app.routers.routes import _ip_args, _validate_destination, _validate_gateway  # noqa: E402


def test_destination_default_allowed() -> None:
    _validate_destination("default", 4)
    _validate_destination("default", 6)


def test_destination_valid_cidr() -> None:
    _validate_destination("10.0.0.0/24", 4)
    _validate_destination("2001:db8::/32", 6)


def test_destination_wrong_family_rejected() -> None:
    with pytest.raises(HTTPException) as e:
        _validate_destination("10.0.0.0/24", 6)
    assert e.value.status_code == 400


def test_destination_garbage_rejected() -> None:
    with pytest.raises(HTTPException):
        _validate_destination("not-an-ip", 4)


def test_gateway_valid() -> None:
    _validate_gateway("192.168.1.1", 4)
    _validate_gateway("fe80::1", 6)


def test_gateway_wrong_family_rejected() -> None:
    with pytest.raises(HTTPException):
        _validate_gateway("fe80::1", 4)


def test_ip_args_requires_gateway_or_device() -> None:
    with pytest.raises(HTTPException):
        _ip_args(IpRouteRequest(family=4, destination="10.0.0.0/24"))


def test_ip_args_with_gateway() -> None:
    args = _ip_args(IpRouteRequest(family=4, destination="default", gateway="192.168.1.1"))
    assert args == ["default", "via", "192.168.1.1"]


def test_ip_args_with_device() -> None:
    args = _ip_args(IpRouteRequest(family=4, destination="10.0.0.0/24", device="eth0"))
    assert args == ["10.0.0.0/24", "dev", "eth0"]


def test_ip_args_with_metric() -> None:
    args = _ip_args(IpRouteRequest(family=4, destination="default", gateway="1.1.1.1", metric=100))
    assert args == ["default", "via", "1.1.1.1", "metric", "100"]
