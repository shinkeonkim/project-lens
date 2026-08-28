"""AdSense Management API v2 래퍼 (docs/ARCHITECTURE.md의 Google Marketing Service).

GA4/GTM/Ads와는 성격이 다르다 — 이 API로 할 수 있는 건 "이미 있는 AdSense 계정의
사이트 연결 상태를 읽는 것"뿐이다. 사이트를 새로 등록하고 광고 게재를 승인하는
과정 자체는 Google이 사람이/정책 기준으로 심사하는 과정이라 API로 우회할 수 없다
(콘솔에서 사이트를 직접 추가해야 함). 그래서 이 모듈은 조회 전용이고, 쓰기 메서드가
없다 — OAuth 스코프도 `adsense.readonly`만 요청한다(google/auth.py SCOPES).
"""

from __future__ import annotations

from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from project_lens.errors import GoogleAPIError, short


@dataclass(frozen=True)
class AdsenseAccount:
    name: str  # "accounts/pub-XXXXXXXXXXXXXXXX"
    display_name: str
    state: str  # "READY" | "NEEDS_ATTENTION" | "CLOSED" 등


@dataclass(frozen=True)
class AdsenseSite:
    name: str  # "accounts/pub-XXXX/sites/example.com"
    domain: str
    state: str  # "READY" | "REQUIRES_REVIEW" | "GETTING_READY" | "NEEDS_ATTENTION" 등
    auto_ads_enabled: bool


def build_client(credentials: Credentials) -> Resource:
    return build("adsense", "v2", credentials=credentials, static_discovery=True)


def list_accounts(service: Resource) -> list[AdsenseAccount]:
    try:
        response = service.accounts().list().execute()
    except HttpError as exc:
        raise GoogleAPIError(f"AdSense 계정 목록 조회 실패: {short(exc)}") from exc

    return [
        AdsenseAccount(
            name=a["name"],
            display_name=a.get("displayName", ""),
            state=a.get("state", "UNKNOWN"),
        )
        for a in response.get("accounts", [])
    ]


def list_sites(service: Resource, *, account_name: str) -> list[AdsenseSite]:
    """account_name은 list_accounts()가 돌려준 "accounts/pub-XXXX" 형태 그대로 넘긴다."""

    try:
        response = service.accounts().sites().list(parent=account_name).execute()
    except HttpError as exc:
        raise GoogleAPIError(f"AdSense 사이트 목록 조회 실패({account_name}): {short(exc)}") from exc

    return [
        AdsenseSite(
            name=s["name"],
            domain=s.get("domain", ""),
            state=s.get("state", "UNKNOWN"),
            auto_ads_enabled=s.get("autoAdsEnabled", False),
        )
        for s in response.get("sites", [])
    ]
