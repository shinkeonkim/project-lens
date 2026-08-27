"""GA4 Data API 래퍼 — 방문자/세션/이탈률 등 성과 지표 조회 전용.

GA4 Admin API(`ga4.py`, 속성/스트림 관리)와는 별개의 Google 서비스다. 리소스 이름
형태(`properties/{id}`)는 같지만 클라이언트/엔드포인트가 다르므로 파일을 분리했다.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.api_core.exceptions import GoogleAPICallError
from google.oauth2.credentials import Credentials

from project_lens.errors import GoogleAPIError

_METRICS = ("activeUsers", "sessions", "screenPageViews", "bounceRate", "averageSessionDuration")


@dataclass(frozen=True)
class Ga4ReportSummary:
    active_users: str
    sessions: str
    page_views: str
    bounce_rate: str
    avg_session_duration_seconds: str


def build_client(credentials: Credentials) -> BetaAnalyticsDataClient:
    return BetaAnalyticsDataClient(credentials=credentials)


def run_summary_report(
    client: BetaAnalyticsDataClient,
    *,
    property_id: str,
    start_date: str = "7daysAgo",
    end_date: str = "today",
) -> Ga4ReportSummary:
    """지정한 기간의 방문자/세션/페이지뷰/이탈률/평균 세션 시간 합계를 조회한다."""

    try:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[Metric(name=name) for name in _METRICS],
        )
        response = client.run_report(request=request)
    except GoogleAPICallError as exc:
        raise GoogleAPIError(f"GA4 리포트 조회 실패(properties/{property_id}): {exc}") from exc

    if not response.rows:
        return Ga4ReportSummary("0", "0", "0", "0", "0")

    values = [metric_value.value for metric_value in response.rows[0].metric_values]
    return Ga4ReportSummary(
        active_users=values[0],
        sessions=values[1],
        page_views=values[2],
        bounce_rate=values[3],
        avg_session_duration_seconds=values[4],
    )
