from __future__ import annotations

import urllib.error

import pytest

from project_lens.health import check_site_health


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_no_url_returns_unknown():
    assert check_site_health(None).status == "unknown"
    assert check_site_health("").status == "unknown"


def test_2xx_response_is_up(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout: _FakeResponse(200)
    )
    result = check_site_health("https://dice-art.example.com")
    assert result.status == "up"
    assert result.http_status == 200


def test_5xx_response_is_down(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout: _FakeResponse(503)
    )
    result = check_site_health("https://broken.example.com")
    assert result.status == "down"
    assert result.http_status == 503


def test_http_error_is_down_with_code(monkeypatch):
    def raise_http_error(req, timeout):
        raise urllib.error.HTTPError("https://x.example.com", 404, "Not Found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", raise_http_error)
    result = check_site_health("https://x.example.com")
    assert result.status == "down"
    assert result.http_status == 404


def test_connection_failure_is_down_without_code(monkeypatch):
    def raise_url_error(req, timeout):
        raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr("urllib.request.urlopen", raise_url_error)
    result = check_site_health("https://does-not-resolve.example.com")
    assert result.status == "down"
    assert result.http_status is None
    assert "Name or service not known" in (result.detail or "")


def test_timeout_is_down(monkeypatch):
    def raise_timeout(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", raise_timeout)
    result = check_site_health("https://slow.example.com")
    assert result.status == "down"
