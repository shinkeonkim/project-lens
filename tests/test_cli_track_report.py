from __future__ import annotations

import pytest
from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.google.ads import AdsReportSummary
from project_lens.google.ga4_reporting import Ga4ReportSummary
from project_lens.registry.db import connect
from project_lens.registry.repository import get_project, upsert_tracking_config

SLUG = "kokoa-lab-dice-art"


@pytest.fixture()
def project_with_ga4(lens_home, fake_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"],
    )
    assert result.exit_code == 0

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        upsert_tracking_config(conn, project_id=proj.id, ga4_property_id="1000")
    finally:
        conn.close()

    return SLUG


def test_report_requires_registered_project(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report", "no-such-slug"])
    assert result.exit_code != 0
    assert "등록되지 않은 프로젝트" in result.output


def test_report_requires_ga4_property(lens_home, fake_repo):
    runner = CliRunner()
    runner.invoke(
        cli.main, ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"]
    )

    result = runner.invoke(cli.main, ["track", "report", SLUG])

    assert result.exit_code != 0
    assert "GA4 속성이 없습니다" in result.output


def test_report_shows_ga4_summary(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")
    monkeypatch.setattr(
        cli.ga4_reporting,
        "run_summary_report",
        lambda client, *, property_id, start_date: Ga4ReportSummary(
            active_users="42",
            sessions="50",
            page_views="120",
            bounce_rate="0.35",
            avg_session_duration_seconds="61.2",
        ),
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report", SLUG])

    assert result.exit_code == 0, result.output
    assert "방문자(활성 사용자): 42" in result.output
    assert "세션: 50" in result.output
    assert "35.0%" in result.output  # 이탈률
    assert "61초" in result.output  # 평균 세션 시간

    conn = connect()
    try:
        run_row = conn.execute("SELECT status FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "success"


def test_report_skips_ads_without_developer_token(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")
    monkeypatch.setattr(
        cli.ga4_reporting,
        "run_summary_report",
        lambda client, *, property_id, start_date: Ga4ReportSummary("1", "1", "1", "0", "0"),
    )
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: False)

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        upsert_tracking_config(conn, project_id=proj.id, ads_customer_id="1112223333")
    finally:
        conn.close()

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report", SLUG])

    assert result.exit_code == 0, result.output
    assert "Developer Token이 없어" in result.output
    assert "Google Ads ---" not in result.output


def test_report_includes_ads_when_available(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")
    monkeypatch.setattr(
        cli.ga4_reporting,
        "run_summary_report",
        lambda client, *, property_id, start_date: Ga4ReportSummary("1", "1", "1", "0", "0"),
    )
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: True)
    monkeypatch.setattr(cli, "load_ads_developer_token", lambda: "dev-token")
    monkeypatch.setattr(cli.ads, "build_client", lambda credentials, **kwargs: "ads-client")
    monkeypatch.setattr(
        cli.ads,
        "run_summary_report",
        lambda client, *, customer_id, date_range: AdsReportSummary(
            impressions=1000, clicks=100, cost_micros=50_000_000, conversions=5.0
        ),
    )

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        upsert_tracking_config(conn, project_id=proj.id, ads_customer_id="1112223333")
    finally:
        conn.close()

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report", SLUG, "--range", "30d"])

    assert result.exit_code == 0, result.output
    assert "노출수: 1000" in result.output
    assert "클릭수: 100" in result.output
    assert "CTR 10.00%" in result.output
    assert "비용: 50.00" in result.output
    assert "전환수: 5.0" in result.output


def test_report_failure_marks_run_failed(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")

    def raise_error(client, *, property_id, start_date):
        from project_lens.errors import GoogleAPIError

        raise GoogleAPIError("boom")

    monkeypatch.setattr(cli.ga4_reporting, "run_summary_report", raise_error)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report", SLUG])

    assert result.exit_code != 0

    conn = connect()
    try:
        run_row = conn.execute("SELECT status, error_code FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "failed"
    assert run_row["error_code"] == "GoogleAPIError"
