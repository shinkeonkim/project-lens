from __future__ import annotations

import pytest
from googleapiclient.errors import HttpError

import project_lens.google.adsense as adsense
from project_lens.errors import GoogleAPIError


class _Exec:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeSites:
    def __init__(self, by_parent, error=None):
        self._by_parent = by_parent
        self._error = error

    def list(self, parent):
        if self._error is not None:
            return _Exec(error=self._error)
        return _Exec({"sites": self._by_parent.get(parent, [])})


class _FakeAccounts:
    def __init__(self, accounts=None, sites_by_parent=None, accounts_error=None, sites_error=None):
        self._accounts = accounts or []
        self._sites_by_parent = sites_by_parent or {}
        self._accounts_error = accounts_error
        self._sites_error = sites_error

    def list(self):
        if self._accounts_error is not None:
            return _Exec(error=self._accounts_error)
        return _Exec({"accounts": self._accounts})

    def sites(self):
        return _FakeSites(self._sites_by_parent, error=self._sites_error)


class _FakeService:
    def __init__(self, **kwargs):
        self._accounts = _FakeAccounts(**kwargs)

    def accounts(self):
        return self._accounts


def _http_error(status=403):
    resp = type("Resp", (), {"status": status, "reason": "Forbidden"})()
    return HttpError(resp, b'{"error": {"message": "insufficient scope"}}')


def test_list_accounts_returns_parsed_accounts():
    service = _FakeService(
        accounts=[
            {"name": "accounts/pub-123", "displayName": "shinkeonkim", "state": "READY"},
        ]
    )

    accounts = adsense.list_accounts(service)

    assert len(accounts) == 1
    assert accounts[0].name == "accounts/pub-123"
    assert accounts[0].display_name == "shinkeonkim"
    assert accounts[0].state == "READY"


def test_list_accounts_empty_when_none_connected():
    service = _FakeService(accounts=[])
    assert adsense.list_accounts(service) == []


def test_list_accounts_wraps_http_error():
    service = _FakeService(accounts_error=_http_error())
    with pytest.raises(GoogleAPIError):
        adsense.list_accounts(service)


def test_list_sites_returns_parsed_sites():
    service = _FakeService(
        sites_by_parent={
            "accounts/pub-123": [
                {
                    "name": "accounts/pub-123/sites/example.com",
                    "domain": "portfolio.shinkeonkim.com",
                    "state": "READY",
                    "autoAdsEnabled": True,
                }
            ]
        }
    )

    sites = adsense.list_sites(service, account_name="accounts/pub-123")

    assert len(sites) == 1
    assert sites[0].domain == "portfolio.shinkeonkim.com"
    assert sites[0].state == "READY"
    assert sites[0].auto_ads_enabled is True


def test_list_sites_empty_when_none_registered():
    service = _FakeService(sites_by_parent={})
    assert adsense.list_sites(service, account_name="accounts/pub-123") == []


def test_list_sites_wraps_http_error():
    service = _FakeService(sites_error=_http_error())
    with pytest.raises(GoogleAPIError):
        adsense.list_sites(service, account_name="accounts/pub-123")
