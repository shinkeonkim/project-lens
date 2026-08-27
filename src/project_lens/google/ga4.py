"""GA4 Admin API 래퍼 (docs/ARCHITECTURE.md의 Google Marketing Service).

모든 함수는 idempotent하게 설계한다 — "없으면 생성, 있으면 조회"로 재실행 안전성을 확보한다
(docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import DataStream, GoogleAdsLink, Property
from google.api_core.exceptions import GoogleAPICallError
from google.oauth2.credentials import Credentials

from project_lens.errors import GoogleAPIError, short


@dataclass(frozen=True)
class Ga4Account:
    id: str
    display_name: str


@dataclass(frozen=True)
class Ga4Property:
    id: str
    name: str  # "properties/123" 형태의 리소스 이름


@dataclass(frozen=True)
class Ga4Stream:
    id: str
    measurement_id: str


@dataclass(frozen=True)
class Ga4GoogleAdsLink:
    name: str  # "properties/123/googleAdsLinks/456"
    customer_id: str


def build_client(credentials: Credentials) -> AnalyticsAdminServiceClient:
    return AnalyticsAdminServiceClient(credentials=credentials)


def list_accounts(client: AnalyticsAdminServiceClient) -> list[Ga4Account]:
    try:
        accounts = client.list_accounts()
        return [
            Ga4Account(id=account.name.removeprefix("accounts/"), display_name=account.display_name)
            for account in accounts
        ]
    except GoogleAPICallError as exc:
        raise GoogleAPIError(f"GA4 계정 목록 조회 실패: {short(exc)}") from exc


def find_or_create_property(
    client: AnalyticsAdminServiceClient,
    *,
    account_id: str,
    display_name: str,
    time_zone: str = "Asia/Seoul",
    currency_code: str = "KRW",
) -> Ga4Property:
    """account_id 아래에서 display_name이 같은 속성을 찾고, 없으면 새로 만든다."""

    parent = f"accounts/{account_id}"
    try:
        existing = list(client.list_properties(request={"filter": f"parent:{parent}"}))
        for prop in existing:
            if prop.display_name == display_name:
                return Ga4Property(id=prop.name.removeprefix("properties/"), name=prop.name)

        created = client.create_property(
            property=Property(
                parent=parent,
                display_name=display_name,
                time_zone=time_zone,
                currency_code=currency_code,
            )
        )
        return Ga4Property(id=created.name.removeprefix("properties/"), name=created.name)
    except GoogleAPICallError as exc:
        raise GoogleAPIError(f"GA4 속성 생성/조회 실패({display_name}): {short(exc)}") from exc


def find_or_create_web_stream(
    client: AnalyticsAdminServiceClient,
    *,
    property_name: str,
    display_name: str,
    default_uri: str,
) -> Ga4Stream:
    """property_name 아래에서 같은 URL을 쓰는 웹 스트림을 찾고, 없으면 새로 만든다."""

    try:
        existing = list(client.list_data_streams(parent=property_name))
        for stream in existing:
            if stream.web_stream_data and stream.web_stream_data.default_uri == default_uri:
                return Ga4Stream(
                    id=stream.name.rsplit("/", 1)[-1],
                    measurement_id=stream.web_stream_data.measurement_id,
                )

        created = client.create_data_stream(
            parent=property_name,
            data_stream=DataStream(
                display_name=display_name,
                type_=DataStream.DataStreamType.WEB_DATA_STREAM,
                web_stream_data=DataStream.WebStreamData(default_uri=default_uri),
            ),
        )
        return Ga4Stream(
            id=created.name.rsplit("/", 1)[-1],
            measurement_id=created.web_stream_data.measurement_id,
        )
    except GoogleAPICallError as exc:
        raise GoogleAPIError(f"GA4 데이터 스트림 생성/조회 실패({display_name}): {short(exc)}") from exc


def ensure_google_ads_link(
    client: AnalyticsAdminServiceClient, *, property_name: str, customer_id: str
) -> Ga4GoogleAdsLink:
    """property_name과 customer_id 사이의 Google Ads 연결을 찾거나 만든다.

    Developer Token 없이 GA4 Admin API만으로 동작한다 (Google Ads API와는 별개 기능).
    """

    try:
        existing = list(client.list_google_ads_links(parent=property_name))
        for link in existing:
            if link.customer_id == customer_id:
                return Ga4GoogleAdsLink(name=link.name, customer_id=link.customer_id)

        created = client.create_google_ads_link(
            parent=property_name, google_ads_link=GoogleAdsLink(customer_id=customer_id)
        )
        return Ga4GoogleAdsLink(name=created.name, customer_id=created.customer_id)
    except GoogleAPICallError as exc:
        raise GoogleAPIError(f"GA4-Ads 연결 생성/조회 실패(customer_id={customer_id}): {short(exc)}") from exc
