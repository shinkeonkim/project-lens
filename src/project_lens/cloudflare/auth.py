"""Cloudflare API 토큰 저장/조회 (docs/SECURITY.md).

Google 자격증명과 동일한 이유로 OS 키체인에만 저장한다 — project-lens 레포나
로컬 평문 파일에는 절대 쓰지 않는다.
"""

from __future__ import annotations

import keyring
import keyring.errors

from project_lens.errors import AuthError

_KEYRING_SERVICE = "project-lens"
_KEYRING_USERNAME = "cloudflare-api-token"


def store_api_token(token: str) -> None:
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, token)


def load_api_token() -> str:
    token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    if token is None:
        raise AuthError(
            "Cloudflare API 토큰이 없습니다. "
            "`lens creds init --provider cloudflare --token <TOKEN>`을 먼저 실행하세요."
        )
    return token


def has_api_token() -> bool:
    return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME) is not None


def clear_api_token() -> None:
    try:
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass
