from app.nm import parse_terse


def test_parse_terse_basic():
    text = "*:HomeNet:82:WPA2:6\n :Neighbor:41:WPA2:11\n"
    rows = parse_terse(text, ["in_use", "ssid", "signal", "security", "chan"])
    assert len(rows) == 2
    assert rows[0]["in_use"] == "*"
    assert rows[0]["ssid"] == "HomeNet"
    assert rows[0]["signal"] == "82"
    assert rows[1]["ssid"] == "Neighbor"


def test_parse_terse_handles_escaped_colon():
    # MAC addresses come back with escaped colons
    text = r"eth0:ethernet:aa\:bb\:cc\:dd\:ee\:ff"
    rows = parse_terse(text, ["dev", "type", "mac"])
    assert rows[0]["mac"] == "aa:bb:cc:dd:ee:ff"


def test_parse_terse_pads_missing_fields():
    text = "solo:only-two-fields"
    rows = parse_terse(text, ["a", "b", "c"])
    assert rows == [{"a": "solo", "b": "only-two-fields", "c": ""}]
