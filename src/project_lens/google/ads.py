"""Google Ads API 래퍼 (docs/ARCHITECTURE.md의 Google Marketing Service).

Developer Token 승인이 필요해 아직 라이브 검증을 하지 못했다 (docs/ROADMAP.md Phase 3).
`google.ads.googleads.client.GoogleAdsClient.get_type()`/`.enums`는 유효한 credentials로
클라이언트를 실제로 만들어야만 동작이 확인 가능해 검증할 방법이 없었다 — 대신 설치된
`google-ads` 패키지(v25)에서 직접 import 가능한 메시지/enum 타입을 써서, 실제 클라이언트
없이도(단위 테스트에서도) 같은 타입으로 검증할 수 있게 했다.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v25.enums.types.conversion_action_category import (
    ConversionActionCategoryEnum,
)
from google.ads.googleads.v25.enums.types.conversion_action_status import (
    ConversionActionStatusEnum,
)
from google.ads.googleads.v25.enums.types.conversion_action_type import ConversionActionTypeEnum
from google.ads.googleads.v25.services.types.conversion_action_service import (
    ConversionActionOperation,
)
from google.oauth2.credentials import Credentials

from project_lens.errors import GoogleAPIError, short


@dataclass(frozen=True)
class AdsConversionAction:
    id: str
    resource_name: str
    name: str


@dataclass(frozen=True)
class AdsReportSummary:
    impressions: int
    clicks: int
    cost_micros: int
    conversions: float

    @property
    def cost(self) -> float:
        return self.cost_micros / 1_000_000


def build_client(
    credentials: Credentials, *, developer_token: str, login_customer_id: str | None = None
) -> GoogleAdsClient:
    config = {
        "developer_token": developer_token,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token,
        "use_proto_plus": True,
    }
    if login_customer_id:
        config["login_customer_id"] = login_customer_id
    return GoogleAdsClient.load_from_dict(config)


def find_or_create_conversion_action(
    client: GoogleAdsClient, *, customer_id: str, name: str
) -> AdsConversionAction:
    """customer_id 아래에서 name이 같은 전환 액션을 찾고, 없으면 웹페이지 전환으로 만든다."""

    try:
        ga_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT conversion_action.id, conversion_action.resource_name, "
            "conversion_action.name FROM conversion_action "
            f"WHERE conversion_action.name = '{_escape_gaql(name)}'"
        )
        for row in ga_service.search(customer_id=customer_id, query=query):
            action = row.conversion_action
            return AdsConversionAction(
                id=str(action.id), resource_name=action.resource_name, name=action.name
            )

        operation = ConversionActionOperation()
        operation.create.name = name
        operation.create.type_ = ConversionActionTypeEnum.ConversionActionType.WEBPAGE
        operation.create.category = ConversionActionCategoryEnum.ConversionActionCategory.DEFAULT
        operation.create.status = ConversionActionStatusEnum.ConversionActionStatus.ENABLED

        conversion_action_service = client.get_service("ConversionActionService")
        response = conversion_action_service.mutate_conversion_actions(
            customer_id=customer_id, operations=[operation]
        )
        resource_name = response.results[0].resource_name
        conversion_action_id = resource_name.rsplit("/", 1)[-1]
        return AdsConversionAction(id=conversion_action_id, resource_name=resource_name, name=name)
    except GoogleAdsException as exc:
        raise GoogleAPIError(f"Ads 전환 액션 생성/조회 실패({name}): {short(exc)}") from exc


_DATE_RANGE_PRESETS = {"7d": "LAST_7_DAYS", "30d": "LAST_30_DAYS"}


def run_summary_report(
    client: GoogleAdsClient, *, customer_id: str, date_range: str = "7d"
) -> AdsReportSummary:
    """customer_id 계정의 지정 기간 노출수/클릭수/비용/전환수 합계를 조회한다."""

    gaql_range = _DATE_RANGE_PRESETS.get(date_range)
    if gaql_range is None:
        raise GoogleAPIError(
            f"지원하지 않는 date_range입니다: {date_range} "
            f"(가능한 값: {', '.join(_DATE_RANGE_PRESETS)})"
        )

    try:
        ga_service = client.get_service("GoogleAdsService")
        query = (
            "SELECT metrics.impressions, metrics.clicks, metrics.cost_micros, "
            "metrics.conversions FROM customer "
            f"WHERE segments.date DURING {gaql_range}"
        )
        impressions = clicks = cost_micros = 0
        conversions = 0.0
        for row in ga_service.search(customer_id=customer_id, query=query):
            impressions += row.metrics.impressions
            clicks += row.metrics.clicks
            cost_micros += row.metrics.cost_micros
            conversions += row.metrics.conversions

        return AdsReportSummary(
            impressions=impressions,
            clicks=clicks,
            cost_micros=cost_micros,
            conversions=conversions,
        )
    except GoogleAdsException as exc:
        raise GoogleAPIError(f"Ads 리포트 조회 실패(customer_id={customer_id}): {short(exc)}") from exc


def _escape_gaql(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
