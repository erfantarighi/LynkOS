import os

os.environ.setdefault("LYNKOS_MOCK_MODE", "true")
os.environ.setdefault("LYNKOS_JWT_SECRET", "test-secret")

from app.adblock import _parse_lines  # noqa: E402


def test_parse_hosts_format() -> None:
    text = """
# StevenBlack comment
0.0.0.0 doubleclick.net
0.0.0.0 google-analytics.com

127.0.0.1 example.com
    """
    domains = _parse_lines(text)
    assert "doubleclick.net" in domains
    assert "google-analytics.com" in domains
    assert "example.com" in domains


def test_parse_bare_domain_format() -> None:
    text = "tracker.example.com\nads.example.org\n"
    domains = _parse_lines(text)
    assert "tracker.example.com" in domains
    assert "ads.example.org" in domains


def test_ignores_localhost_markers() -> None:
    text = """
127.0.0.1 localhost
0.0.0.0 broadcasthost
0.0.0.0 local
"""
    domains = _parse_lines(text)
    assert not domains


def test_rejects_invalid_domains() -> None:
    text = """
0.0.0.0 not a domain
0.0.0.0 no-tld
0.0.0.0 -starts.with.hyphen.com
0.0.0.0 valid.example.com
"""
    domains = _parse_lines(text)
    assert "valid.example.com" in domains
    assert "not" not in domains
    assert "no-tld" not in domains


def test_ignores_comments_and_blank_lines() -> None:
    text = "# comment\n\n0.0.0.0 a.com  # inline comment\n"
    domains = _parse_lines(text)
    assert "a.com" in domains


def test_write_hosts_filters_allowlist(tmp_path, monkeypatch) -> None:
    from app import adblock
    monkeypatch.setattr(adblock, "HOSTS_DIR", tmp_path)
    monkeypatch.setattr(adblock, "HOSTS_FILE", tmp_path / "hosts")
    count = adblock.write_hosts({"ads.com", "trackers.com", "safe.com"}, {"safe.com"})
    assert count == 2
    content = (tmp_path / "hosts").read_text()
    assert "safe.com" not in content
    assert "0.0.0.0 ads.com" in content
    assert "0.0.0.0 trackers.com" in content
