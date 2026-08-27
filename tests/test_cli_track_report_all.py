from __future__ import annotations

import pytest
from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.google.ga4_reporting import Ga4ReportSummary
from project_lens.registry.db import connect
from project_lens.registry.repository import upsert_project, upsert_tracking_config


def _register_two_projects_with_ga4(conn):
    dice_art = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )
    upsert_tracking_config(conn, project_id=dice_art.id, ga4_property_id="1000")

    my_cv = upsert_project(
        conn,
        github_url="https://github.com/shinkeonkim/my-cv",
        github_org="shinkeonkim",
        github_repo="my-cv",
        visibility="public",
        default_branch="main",
    )
    upsert_tracking_config(conn, project_id=my_cv.id, ga4_property_id="2000")

    # GA4가 아직 없는 프로젝트 — 건너뛰어야 함
    upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/pattern-type",
        github_org="kokoa-lab",
        github_repo="pattern-type",
        visibility="public",
        default_branch="main",
    )


def test_report_all_with_no_projects(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report-all"])

    assert result.exit_code == 0, result.output
    assert "GA4가 세팅된 프로젝트가 없습니다" in result.output


def test_report_all_aggregates_multiple_projects(lens_home, monkeypatch):
    conn = connect()
    try:
        _register_two_projects_with_ga4(conn)
    finally:
        conn.close()

    monkeypatch.setattr(cli, "load_credentials", lambda: object())

    def fake_run_summary_report(client, *, property_id, start_date):
        values = {"1000": "10", "2000": "20"}
        return Ga4ReportSummary(
            active_users=values[property_id],
            sessions="1",
            page_views="1",
            bounce_rate="0",
            avg_session_duration_seconds="0",
        )

    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")
    monkeypatch.setattr(cli.ga4_reporting, "run_summary_report", fake_run_summary_report)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report-all"])

    assert result.exit_code == 0, result.output
    assert "kokoa-lab-dice-art" in result.output
    assert "shinkeonkim-my-cv" in result.output
    assert "방문자(활성 사용자): 10" in result.output
    assert "방문자(활성 사용자): 20" in result.output
    assert "1개 프로젝트는 GA4가 아직 없어 건너뜀" in result.output
    assert "저장됨:" in result.output

    conn = connect()
    try:
        rows = conn.execute("SELECT status FROM deploy_runs WHERE run_type = 'report'").fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert all(r["status"] == "success" for r in rows)


def test_report_all_continues_past_per_project_failure(lens_home, monkeypatch):
    conn = connect()
    try:
        _register_two_projects_with_ga4(conn)
    finally:
        conn.close()

    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")

    def fake_run_summary_report(client, *, property_id, start_date):
        if property_id == "1000":
            from project_lens.errors import GoogleAPIError

            raise GoogleAPIError("boom")
        return Ga4ReportSummary("20", "1", "1", "0", "0")

    monkeypatch.setattr(cli.ga4_reporting, "run_summary_report", fake_run_summary_report)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report-all"])

    assert result.exit_code == 0, result.output
    assert "shinkeonkim-my-cv" in result.output
    assert "조회 실패:" in result.output
    assert "kokoa-lab-dice-art: GoogleAPIError" in result.output

    conn = connect()
    try:
        statuses = {
            r["status"]
            for r in conn.execute("SELECT status FROM deploy_runs WHERE run_type = 'report'")
        }
    finally:
        conn.close()
    assert statuses == {"success", "failed"}


def test_report_all_writes_file_to_reports_dir(lens_home, monkeypatch):
    from project_lens.config import reports_dir

    conn = connect()
    try:
        _register_two_projects_with_ga4(conn)
    finally:
        conn.close()

    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli.ga4_reporting, "build_client", lambda credentials: "data-client")
    monkeypatch.setattr(
        cli.ga4_reporting,
        "run_summary_report",
        lambda client, *, property_id, start_date: Ga4ReportSummary("1", "1", "1", "0", "0"),
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "report-all"])

    assert result.exit_code == 0, result.output
    files = list(reports_dir().glob("*.txt"))
    assert len(files) == 1
    assert "kokoa-lab-dice-art" in files[0].read_text()
