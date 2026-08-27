from __future__ import annotations

from google.analytics.data_v1beta.types import (
    MetricValue,
    Row,
    RunReportRequest,
    RunReportResponse,
)

import project_lens.google.ga4_reporting as ga4_reporting


class FakeDataClient:
    def __init__(self, values: list[str] | None):
        self._values = values
        self.last_request: RunReportRequest | None = None

    def run_report(self, request: RunReportRequest) -> RunReportResponse:
        self.last_request = request
        if self._values is None:
            return RunReportResponse(rows=[])
        return RunReportResponse(rows=[Row(metric_values=[MetricValue(value=v) for v in self._values])])


def test_run_summary_report_maps_metrics_in_order():
    client = FakeDataClient(["123", "45", "678", "0.42", "39.5"])

    summary = ga4_reporting.run_summary_report(client, property_id="1000")

    assert summary.active_users == "123"
    assert summary.sessions == "45"
    assert summary.page_views == "678"
    assert summary.bounce_rate == "0.42"
    assert summary.avg_session_duration_seconds == "39.5"


def test_run_summary_report_uses_correct_property_and_date_range():
    client = FakeDataClient(["0", "0", "0", "0", "0"])

    ga4_reporting.run_summary_report(
        client, property_id="1000", start_date="30daysAgo", end_date="today"
    )

    assert client.last_request.property == "properties/1000"
    assert client.last_request.date_ranges[0].start_date == "30daysAgo"
    assert client.last_request.date_ranges[0].end_date == "today"
    assert [m.name for m in client.last_request.metrics] == [
        "activeUsers",
        "sessions",
        "screenPageViews",
        "bounceRate",
        "averageSessionDuration",
    ]


def test_run_summary_report_returns_zeros_when_no_data():
    client = FakeDataClient(None)

    summary = ga4_reporting.run_summary_report(client, property_id="1000")

    assert summary.active_users == "0"
    assert summary.sessions == "0"
