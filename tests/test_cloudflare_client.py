from __future__ import annotations

import json
import urllib.error

import pytest

from project_lens.cloudflare import client
from project_lens.errors import CloudflareAPIError


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _ok(result):
    return {"success": True, "errors": [], "result": result}


def test_get_zone_returns_first_match(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeResponse(_ok([{"id": "zone123", "name": "xn--hy1by51c.kr"}])),
    )
    zone = client.get_zone("tok", "xn--hy1by51c.kr")
    assert zone.id == "zone123"
    assert zone.name == "xn--hy1by51c.kr"


def test_get_zone_raises_when_not_found(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(_ok([])))
    with pytest.raises(CloudflareAPIError):
        client.get_zone("tok", "does-not-exist.kr")


def test_upsert_dns_record_creates_when_none_exists(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url))
        if req.get_method() == "GET":
            return _FakeResponse(_ok([]))
        return _FakeResponse(_ok({"id": "rec1", "name": "boj.xn--hy1by51c.kr"}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = client.upsert_dns_record(
        "tok", "zone123", record_type="CNAME", name="boj.xn--hy1by51c.kr", content="tunnel.example.com"
    )
    assert result["id"] == "rec1"
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"


def test_upsert_dns_record_updates_when_exists(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url))
        if req.get_method() == "GET":
            return _FakeResponse(_ok([{"id": "rec1", "name": "boj.xn--hy1by51c.kr"}]))
        return _FakeResponse(_ok({"id": "rec1", "name": "boj.xn--hy1by51c.kr"}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client.upsert_dns_record(
        "tok", "zone123", record_type="CNAME", name="boj.xn--hy1by51c.kr", content="tunnel.example.com"
    )
    assert calls[1][0] == "PUT"
    assert "rec1" in calls[1][1]


def test_request_raises_on_api_error_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeResponse(
            {"success": False, "errors": [{"message": "Invalid token"}], "result": None}
        ),
    )
    with pytest.raises(CloudflareAPIError, match="Invalid token"):
        client.list_accounts("bad-token")


def test_request_raises_on_http_error(monkeypatch):
    def raise_http_error(req, timeout):
        body = json.dumps({"errors": [{"message": "Forbidden"}]}).encode()
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, __import__("io").BytesIO(body))

    monkeypatch.setattr("urllib.request.urlopen", raise_http_error)
    with pytest.raises(CloudflareAPIError, match="Forbidden"):
        client.list_accounts("tok")


def test_add_tunnel_public_hostname_inserts_before_catch_all(monkeypatch):
    existing_config = {
        "ingress": [
            {"hostname": "url-shortener.shinkeonkim.com", "service": "http://url-shortener:8080"},
            {"service": "http_status:404"},
        ]
    }
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url, req.data))
        if req.get_method() == "GET":
            return _FakeResponse(_ok({"config": existing_config}))
        return _FakeResponse(_ok({"config": json.loads(req.data)["config"]}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = client.add_tunnel_public_hostname(
        "tok", "acct1", "tunnel1", hostname="boj.xn--hy1by51c.kr", service="http://boj-archive:80"
    )

    ingress = result["config"]["ingress"]
    assert ingress[-1] == {"service": "http_status:404"}
    assert {"hostname": "boj.xn--hy1by51c.kr", "service": "http://boj-archive:80"} in ingress[:-1]
    assert len(ingress) == 3


def test_add_tunnel_public_hostname_replaces_existing_same_hostname(monkeypatch):
    existing_config = {
        "ingress": [
            {"hostname": "boj.xn--hy1by51c.kr", "service": "http://old-target:80"},
            {"service": "http_status:404"},
        ]
    }

    def fake_urlopen(req, timeout):
        if req.get_method() == "GET":
            return _FakeResponse(_ok({"config": existing_config}))
        return _FakeResponse(_ok({"config": json.loads(req.data)["config"]}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = client.add_tunnel_public_hostname(
        "tok", "acct1", "tunnel1", hostname="boj.xn--hy1by51c.kr", service="http://new-target:80"
    )

    ingress = result["config"]["ingress"]
    assert len(ingress) == 2
    assert ingress[0] == {"hostname": "boj.xn--hy1by51c.kr", "service": "http://new-target:80"}
