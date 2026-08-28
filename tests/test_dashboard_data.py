from __future__ import annotations

from types import SimpleNamespace

import pytest

from project_lens import dashboard_data
from project_lens.registry.db import connect
from project_lens.registry.repository import (
    finish_run,
    start_run,
    upsert_project,
    upsert_tracking_config,
)


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "test.sqlite3")
    yield connection
    connection.close()


def _add_project(conn, slug_repo="dice-art", **tracking_kwargs):
    record = upsert_project(
        conn,
        github_url=f"https://github.com/kokoa-lab/{slug_repo}",
        github_org="kokoa-lab",
        github_repo=slug_repo,
        visibility="public",
        default_branch="main",
        site_url=f"https://{slug_repo}.example.com",
    )
    if tracking_kwargs:
        upsert_tracking_config(conn, project_id=record.id, **tracking_kwargs)
    return record


def test_collect_dashboard_rows_offline_skips_ga4(conn, monkeypatch):
    record = _add_project(conn, ga4_property_id="12345")
    run_id = start_run(conn, project_id=record.id, run_type="sync")
    finish_run(conn, run_id, status="success", pr_url="https://github.com/kokoa-lab/dice-art/pull/1")

    monkeypatch.setattr(dashboard_data, "pr_state", lambda url: "OPEN")

    rows = dashboard_data.collect_dashboard_rows(conn, offline=True)

    assert len(rows) == 1
    row = rows[0]
    assert row.slug == record.slug
    assert row.pr_url == "https://github.com/kokoa-lab/dice-art/pull/1"
    assert row.pr_state == "OPEN"
    assert row.ga4_active_users_7d is None  # offline이면 GA4 API를 아예 안 부른다


def test_collect_dashboard_rows_fetches_ga4_when_online(conn, monkeypatch):
    _add_project(conn, ga4_property_id="12345", ga4_measurement_id="G-ABC123")

    monkeypatch.setattr(dashboard_data, "pr_state", lambda url: None)
    monkeypatch.setattr(dashboard_data, "load_credentials", lambda: object())
    monkeypatch.setattr(
        dashboard_data.ga4_reporting, "build_client", lambda credentials: SimpleNamespace()
    )
    monkeypatch.setattr(
        dashboard_data.ga4_reporting,
        "run_summary_report",
        lambda client, *, property_id, start_date: SimpleNamespace(active_users="7", sessions="9"),
    )

    rows = dashboard_data.collect_dashboard_rows(conn, offline=False)

    assert rows[0].ga4_active_users_7d == "7"
    assert rows[0].ga4_sessions_7d == "9"


def test_collect_dashboard_rows_survives_ga4_failure_for_one_project(conn, monkeypatch):
    """한 프로젝트의 GA4 조회가 실패해도 나머지 프로젝트/전체 대시보드 생성은 계속돼야 한다."""

    _add_project(conn, slug_repo="dice-art", ga4_property_id="111")
    _add_project(conn, slug_repo="cozy-hive", ga4_property_id="222")

    monkeypatch.setattr(dashboard_data, "pr_state", lambda url: None)
    monkeypatch.setattr(dashboard_data, "load_credentials", lambda: object())
    monkeypatch.setattr(
        dashboard_data.ga4_reporting, "build_client", lambda credentials: SimpleNamespace()
    )

    def flaky_report(client, *, property_id, start_date):
        if property_id == "111":
            raise RuntimeError("GA4 quota exceeded")
        return SimpleNamespace(active_users="3", sessions="4")

    monkeypatch.setattr(dashboard_data.ga4_reporting, "run_summary_report", flaky_report)

    rows = dashboard_data.collect_dashboard_rows(conn, offline=False)

    by_slug = {r.slug: r for r in rows}
    assert by_slug["kokoa-lab-dice-art"].ga4_active_users_7d is None
    assert by_slug["kokoa-lab-cozy-hive"].ga4_active_users_7d == "3"


def test_collect_dashboard_rows_empty_registry_returns_empty_list(conn, monkeypatch):
    monkeypatch.setattr(dashboard_data, "pr_state", lambda url: None)
    assert dashboard_data.collect_dashboard_rows(conn, offline=True) == []
