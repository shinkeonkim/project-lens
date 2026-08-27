from __future__ import annotations

import pytest

from project_lens.registry.db import connect
from project_lens.registry.repository import (
    finish_run,
    get_project,
    get_run,
    get_tracking_config,
    list_projects,
    set_project_status,
    set_site_url,
    slugify,
    start_run,
    upsert_project,
    upsert_tracking_config,
)


@pytest.mark.parametrize(
    "org,repo,expected",
    [
        ("kokoa-lab", "dice-art", "kokoa-lab-dice-art"),
        ("shinkeonkim", "my-portfolio", "shinkeonkim-my-portfolio"),
        ("Kokoa_Study.Room", "Weird Name!", "kokoa-study-room-weird-name"),
    ],
)
def test_slugify(org, repo, expected):
    assert slugify(org, repo) == expected


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "test.sqlite3")
    yield connection
    connection.close()


def test_upsert_project_creates_new_record(conn):
    record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
        deployment_type="cloudflare_workers",
    )

    assert record.slug == "kokoa-lab-dice-art"
    assert record.status == "pending"
    assert record.deployment_type == "cloudflare_workers"
    assert len(list_projects(conn)) == 1


def test_upsert_project_is_idempotent(conn):
    first = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )
    second = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
        deployment_type="cloudflare_workers",
    )

    assert first.id == second.id
    assert second.deployment_type == "cloudflare_workers"
    assert len(list_projects(conn)) == 1


def test_get_project_missing_returns_none(conn):
    assert get_project(conn, "does-not-exist") is None


def test_list_projects_sorted_by_slug(conn):
    upsert_project(
        conn,
        github_url="https://github.com/shinkeonkim/my-portfolio",
        github_org="shinkeonkim",
        github_repo="my-portfolio",
        visibility="public",
        default_branch="main",
    )
    upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    slugs = [p.slug for p in list_projects(conn)]
    assert slugs == sorted(slugs)


def test_set_project_status(conn):
    record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    set_project_status(conn, record.slug, "needs_attention")

    assert get_project(conn, record.slug).status == "needs_attention"


def test_run_lifecycle_success(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    run_id = start_run(conn, project_id=project_record.id, run_type="sync")
    running = get_run(conn, run_id)
    assert running.status == "running"
    assert running.finished_at is None

    finish_run(
        conn,
        run_id,
        status="success",
        commit_sha="abc123",
        pr_url="https://github.com/kokoa-lab/dice-art/pull/1",
        summary="GTM 스니펫 삽입",
    )

    finished = get_run(conn, run_id)
    assert finished.status == "success"
    assert finished.commit_sha == "abc123"
    assert finished.pr_url == "https://github.com/kokoa-lab/dice-art/pull/1"
    assert finished.finished_at is not None


def test_run_lifecycle_failure(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    run_id = start_run(conn, project_id=project_record.id, run_type="sync")
    finish_run(
        conn,
        run_id,
        status="failed",
        error_code="AdapterDetectionError",
        error_summary="배포 방식을 감지하지 못했습니다.",
    )

    finished = get_run(conn, run_id)
    assert finished.status == "failed"
    assert finished.error_code == "AdapterDetectionError"


def test_get_run_missing_returns_none(conn):
    assert get_run(conn, 999) is None


def test_set_site_url(conn):
    record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )
    assert record.site_url is None

    set_site_url(conn, record.slug, "https://dice-art.example.com")

    assert get_project(conn, record.slug).site_url == "https://dice-art.example.com"


def test_upsert_project_site_url_does_not_clobber_existing(conn):
    first = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
        site_url="https://dice-art.example.com",
    )
    second = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    assert first.site_url == "https://dice-art.example.com"
    assert second.site_url == "https://dice-art.example.com"


def test_upsert_tracking_config_creates_and_updates(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    created = upsert_tracking_config(
        conn,
        project_id=project_record.id,
        ga4_account_id="111",
        ga4_property_id="1000",
        ga4_measurement_id="G-ABC123",
        ga4_stream_id="2000",
        gtm_account_id="222",
        gtm_container_id="3000",
        gtm_workspace_id="1",
        gtm_last_published_version="1",
    )

    assert created.ga4_measurement_id == "G-ABC123"
    assert created.gtm_container_id == "3000"
    assert created.config_version == 1

    updated = upsert_tracking_config(
        conn,
        project_id=project_record.id,
        gtm_last_published_version="2",
    )

    assert updated.id == created.id
    assert updated.gtm_last_published_version == "2"
    # 넘기지 않은 필드는 기존 값을 유지해야 함
    assert updated.ga4_measurement_id == "G-ABC123"
    assert updated.gtm_container_id == "3000"


def test_get_tracking_config_missing_returns_none(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )
    assert get_tracking_config(conn, project_record.id) is None


def test_upsert_tracking_config_defaults_ads_fields_to_empty(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    created = upsert_tracking_config(conn, project_id=project_record.id, ga4_property_id="1000")

    assert created.ads_customer_id is None
    assert created.ads_conversion_action_ids == "[]"


def test_upsert_tracking_config_ads_fields_replace_not_merge(conn):
    project_record = upsert_project(
        conn,
        github_url="https://github.com/kokoa-lab/dice-art",
        github_org="kokoa-lab",
        github_repo="dice-art",
        visibility="public",
        default_branch="main",
    )

    upsert_tracking_config(
        conn,
        project_id=project_record.id,
        ads_customer_id="1112223333",
        ads_conversion_action_ids='["customers/111/conversionActions/1"]',
    )
    updated = upsert_tracking_config(
        conn,
        project_id=project_record.id,
        ads_conversion_action_ids='["customers/111/conversionActions/1", "customers/111/conversionActions/2"]',
    )

    assert updated.ads_customer_id == "1112223333"  # None으로 넘긴 필드는 유지됨
    assert updated.ads_conversion_action_ids == (
        '["customers/111/conversionActions/1", "customers/111/conversionActions/2"]'
    )
