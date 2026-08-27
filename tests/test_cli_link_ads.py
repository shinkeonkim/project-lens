from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.google.ads import AdsConversionAction
from project_lens.google.ga4 import Ga4GoogleAdsLink
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


def test_link_ads_requires_registered_project(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "link-ads", "no-such-slug", "--customer-id", "111"])
    assert result.exit_code != 0
    assert "등록되지 않은 프로젝트" in result.output


def test_link_ads_requires_ga4_property(lens_home, fake_repo):
    runner = CliRunner()
    runner.invoke(
        cli.main, ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"]
    )

    result = runner.invoke(cli.main, ["track", "link-ads", SLUG, "--customer-id", "111"])

    assert result.exit_code != 0
    assert "GA4 속성이 없습니다" in result.output


def test_link_ads_dry_run_makes_no_calls(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: pytest.fail("dry-run에서 호출되면 안 됨"))
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: False)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "link-ads", SLUG, "--customer-id", "1112223333"])

    assert result.exit_code == 0, result.output
    assert "[dry-run]" in result.output
    assert "1112223333" in result.output

    conn = connect()
    try:
        count = conn.execute("SELECT COUNT(*) FROM deploy_runs").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_link_ads_yes_without_developer_token_skips_conversion_action(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: False)
    monkeypatch.setattr(cli.ga4, "build_client", lambda credentials: "ga4-client")
    link_calls = []
    monkeypatch.setattr(
        cli.ga4,
        "ensure_google_ads_link",
        lambda client, *, property_name, customer_id: link_calls.append(
            (property_name, customer_id)
        )
        or Ga4GoogleAdsLink(name=f"{property_name}/googleAdsLinks/1", customer_id=customer_id),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.main, ["track", "link-ads", SLUG, "--customer-id", "1112223333", "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert link_calls == [("properties/1000", "1112223333")]
    assert "전환 액션" not in result.output

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        row = conn.execute(
            "SELECT ads_customer_id, ads_conversion_action_ids FROM tracking_configs WHERE project_id = ?",
            (proj.id,),
        ).fetchone()
        run_row = conn.execute("SELECT status FROM deploy_runs").fetchone()
    finally:
        conn.close()

    assert row["ads_customer_id"] == "1112223333"
    assert json.loads(row["ads_conversion_action_ids"]) == []
    assert run_row["status"] == "success"


def test_link_ads_yes_with_developer_token_creates_conversion_action(project_with_ga4, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: True)
    monkeypatch.setattr(cli, "load_ads_developer_token", lambda: "dev-token")
    monkeypatch.setattr(cli.ga4, "build_client", lambda credentials: "ga4-client")
    monkeypatch.setattr(
        cli.ga4,
        "ensure_google_ads_link",
        lambda client, *, property_name, customer_id: Ga4GoogleAdsLink(
            name=f"{property_name}/googleAdsLinks/1", customer_id=customer_id
        ),
    )
    monkeypatch.setattr(cli.ads, "build_client", lambda credentials, **kwargs: "ads-client")
    monkeypatch.setattr(
        cli.ads,
        "find_or_create_conversion_action",
        lambda client, *, customer_id, name: AdsConversionAction(
            id="999",
            resource_name=f"customers/{customer_id}/conversionActions/999",
            name=name,
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.main, ["track", "link-ads", SLUG, "--customer-id", "1112223333", "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert "customers/1112223333/conversionActions/999" in result.output

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        row = conn.execute(
            "SELECT ads_conversion_action_ids FROM tracking_configs WHERE project_id = ?",
            (proj.id,),
        ).fetchone()
    finally:
        conn.close()

    assert json.loads(row["ads_conversion_action_ids"]) == [
        "customers/1112223333/conversionActions/999"
    ]


def test_link_ads_failure_marks_run_failed(project_with_ga4, monkeypatch):
    from project_lens.errors import GoogleAPIError

    monkeypatch.setattr(cli, "load_credentials", lambda: object())
    monkeypatch.setattr(cli, "has_ads_developer_token", lambda: False)
    monkeypatch.setattr(cli.ga4, "build_client", lambda credentials: "ga4-client")

    def raise_error(client, *, property_name, customer_id):
        raise GoogleAPIError("연결 실패")

    monkeypatch.setattr(cli.ga4, "ensure_google_ads_link", raise_error)

    runner = CliRunner()
    result = runner.invoke(
        cli.main, ["track", "link-ads", SLUG, "--customer-id", "1112223333", "--yes"]
    )

    assert result.exit_code != 0

    conn = connect()
    try:
        run_row = conn.execute("SELECT status, error_code FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "failed"
    assert run_row["error_code"] == "GoogleAPIError"
