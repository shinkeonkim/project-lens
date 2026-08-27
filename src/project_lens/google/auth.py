"""Google OAuth 인증 (docs/SECURITY.md).

refresh token은 project-lens 레포나 로컬 평문 파일이 아니라 OS 키체인(keyring)에만 저장한다.
client_id/client_secret은 사용자가 GCP 콘솔에서 직접 발급받아 로컬 파일로 배치한다 —
project-lens는 자체 OAuth 클라이언트를 내장하지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import keyring
import keyring.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from project_lens.config import credentials_dir
from project_lens.errors import AuthError

_KEYRING_SERVICE = "project-lens"
_KEYRING_USERNAME = "google-oauth-credentials"

SCOPES = [
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/tagmanager.manage.accounts",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/tagmanager.edit.containerversions",
    "https://www.googleapis.com/auth/tagmanager.publish",
]


def client_secret_path() -> Path:
    return credentials_dir() / "google_oauth_client.json"


def run_oauth_flow() -> Credentials:
    """최초 1회 브라우저 동의 플로우를 실행하고 결과를 keyring에 저장한다."""

    secret_path = client_secret_path()
    if not secret_path.exists():
        raise AuthError(
            f"Google OAuth 클라이언트 파일이 없습니다: {secret_path}\n"
            "docs/SECURITY.md 안내대로 GCP 콘솔에서 '데스크톱 앱' OAuth 클라이언트를 만들고 "
            "다운로드한 JSON을 이 경로에 저장한 뒤 다시 시도하세요."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), scopes=SCOPES)
    credentials = flow.run_local_server(port=0)
    _store_credentials(credentials)
    return credentials


def load_credentials() -> Credentials:
    """keyring에 저장된 credentials를 불러오고, 만료됐으면 갱신한다."""

    raw = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    if raw is None:
        raise AuthError(
            "Google 인증 정보가 없습니다. `lens creds init --provider google`을 먼저 실행하세요."
        )

    credentials = Credentials.from_authorized_user_info(json.loads(raw), scopes=SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _store_credentials(credentials)

    return credentials


def has_stored_credentials() -> bool:
    return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME) is not None


def clear_credentials() -> None:
    try:
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


def _store_credentials(credentials: Credentials) -> None:
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, credentials.to_json())
