from __future__ import annotations

import datetime
import json

import pytest
from google.oauth2.credentials import Credentials

import project_lens.google.auth as auth
from project_lens.errors import AuthError


def _valid_credentials_json() -> str:
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    return _credentials_json(future)


def _expired_credentials_json() -> str:
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    return _credentials_json(past)


def _credentials_json(expiry: datetime.datetime) -> str:
    creds = Credentials(
        token="t",
        refresh_token="r",
        client_id="cid",
        client_secret="cs",
        token_uri="https://oauth2.googleapis.com/token",
        expiry=expiry,
    )
    return creds.to_json()


_VALID_INFO = {
    "token": "t",
    "refresh_token": "r",
    "client_id": "cid",
    "client_secret": "cs",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def test_run_oauth_flow_raises_when_client_secret_missing(lens_home, fake_keyring):
    with pytest.raises(AuthError):
        auth.run_oauth_flow()


def test_run_oauth_flow_stores_credentials(lens_home, fake_keyring, monkeypatch):
    auth.client_secret_path().write_text("{}", encoding="utf-8")

    class FakeCredentials:
        def to_json(self):
            return json.dumps(_VALID_INFO)

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            assert scopes == auth.SCOPES
            return cls()

        def run_local_server(self, port):
            return FakeCredentials()

    monkeypatch.setattr(auth, "InstalledAppFlow", FakeFlow)

    auth.run_oauth_flow()

    assert fake_keyring.get_password(auth._KEYRING_SERVICE, auth._KEYRING_USERNAME) is not None
    assert auth.has_stored_credentials() is True


def test_load_credentials_raises_when_not_authenticated(lens_home, fake_keyring):
    with pytest.raises(AuthError):
        auth.load_credentials()


def test_load_credentials_returns_valid_stored_credentials(lens_home, fake_keyring):
    fake_keyring.set_password(auth._KEYRING_SERVICE, auth._KEYRING_USERNAME, _valid_credentials_json())

    credentials = auth.load_credentials()

    assert credentials.refresh_token == "r"
    assert credentials.expired is False


def test_load_credentials_refreshes_expired_and_restores(lens_home, fake_keyring, monkeypatch):
    fake_keyring.set_password(
        auth._KEYRING_SERVICE, auth._KEYRING_USERNAME, _expired_credentials_json()
    )

    def fake_refresh(self, request):
        self.token = "refreshed"
        self.expiry = None  # 더 이상 만료되지 않은 것으로 취급

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)

    credentials = auth.load_credentials()

    assert credentials.token == "refreshed"
    stored = json.loads(fake_keyring.get_password(auth._KEYRING_SERVICE, auth._KEYRING_USERNAME))
    assert stored["token"] == "refreshed"


def test_clear_credentials_removes_stored_value(lens_home, fake_keyring):
    fake_keyring.set_password(auth._KEYRING_SERVICE, auth._KEYRING_USERNAME, json.dumps(_VALID_INFO))
    auth.clear_credentials()
    assert auth.has_stored_credentials() is False


def test_clear_credentials_is_noop_when_nothing_stored(lens_home, fake_keyring):
    auth.clear_credentials()  # 예외 없이 통과해야 함
