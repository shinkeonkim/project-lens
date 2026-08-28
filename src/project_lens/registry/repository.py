from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from project_lens.registry.models import DeployRun, Project, TrackingConfig


def slugify(org: str, repo: str) -> str:
    raw = f"{org}-{repo}".lower()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_project(
    conn: sqlite3.Connection,
    *,
    github_url: str,
    github_org: str,
    github_repo: str,
    visibility: str,
    default_branch: str,
    deployment_type: str = "unknown",
    deploy_mode: str = "pr",
    notes: str = "",
    site_url: str | None = None,
) -> Project:
    """slug 기준으로 존재하면 갱신, 없으면 신규 등록한다 (재실행 안전)."""

    slug = slugify(github_org, github_repo)
    now = _now()
    conn.execute(
        """
        INSERT INTO projects (
            slug, name, github_url, github_org, github_repo,
            visibility, default_branch, deployment_type, deploy_mode,
            status, notes, site_url, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            github_url = excluded.github_url,
            visibility = excluded.visibility,
            default_branch = excluded.default_branch,
            deployment_type = excluded.deployment_type,
            site_url = COALESCE(excluded.site_url, projects.site_url),
            updated_at = excluded.updated_at
        """,
        (
            slug,
            github_repo,
            github_url,
            github_org,
            github_repo,
            visibility,
            default_branch,
            deployment_type,
            deploy_mode,
            notes,
            site_url,
            now,
            now,
        ),
    )
    conn.commit()
    return get_project(conn, slug)  # type: ignore[return-value]


def set_site_url(conn: sqlite3.Connection, slug: str, site_url: str) -> None:
    conn.execute(
        "UPDATE projects SET site_url = ?, updated_at = ? WHERE slug = ?",
        (site_url, _now(), slug),
    )
    conn.commit()


def set_ads_policy(conn: sqlite3.Connection, slug: str, ads_policy: str) -> None:
    """ads_policy는 'allowed' | 'excluded' | 'unreviewed' 중 하나여야 한다(CHECK 제약).

    새로 등록되는 프로젝트는 기본값 'unreviewed'다 — 검토 없이 자동으로 광고 대상에
    들어가지 않게 하기 위해 의도적으로 이렇게 만들었다(포트폴리오/이력서 같은 개인
    브랜드 사이트에 실수로 광고가 붙으면 안 되기 때문).
    """

    conn.execute(
        "UPDATE projects SET ads_policy = ?, updated_at = ? WHERE slug = ?",
        (ads_policy, _now(), slug),
    )
    conn.commit()


def get_project(conn: sqlite3.Connection, slug: str) -> Project | None:
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    return Project.from_row(row) if row else None


def list_projects(conn: sqlite3.Connection) -> list[Project]:
    rows = conn.execute("SELECT * FROM projects ORDER BY slug").fetchall()
    return [Project.from_row(row) for row in rows]


def set_project_status(conn: sqlite3.Connection, slug: str, status: str) -> None:
    conn.execute(
        "UPDATE projects SET status = ?, updated_at = ? WHERE slug = ?",
        (status, _now(), slug),
    )
    conn.commit()


def start_run(conn: sqlite3.Connection, *, project_id: int, run_type: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO deploy_runs (project_id, run_type, status, started_at)
        VALUES (?, ?, 'running', ?)
        """,
        (project_id, run_type, _now()),
    )
    conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    commit_sha: str | None = None,
    pr_url: str | None = None,
    summary: str | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE deploy_runs
        SET status = ?, finished_at = ?, commit_sha = ?, pr_url = ?,
            summary = ?, error_code = ?, error_summary = ?
        WHERE id = ?
        """,
        (status, _now(), commit_sha, pr_url, summary, error_code, error_summary, run_id),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: int) -> DeployRun | None:
    row = conn.execute("SELECT * FROM deploy_runs WHERE id = ?", (run_id,)).fetchone()
    return DeployRun.from_row(row) if row else None


def get_latest_run(conn: sqlite3.Connection, project_id: int) -> DeployRun | None:
    row = conn.execute(
        "SELECT * FROM deploy_runs WHERE project_id = ? ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return DeployRun.from_row(row) if row else None


def get_latest_pr_run(conn: sqlite3.Connection, project_id: int) -> DeployRun | None:
    """PR이 실제로 만들어진 가장 최근 run을 찾는다.

    `get_latest_run`은 run_type을 안 가리므로, sync 이후에 report 같은 run이 쌓이면
    (pr_url이 없는 run이 더 최근이 되어) PR 정보가 가려진다 — 대시보드처럼 "그 프로젝트에
    PR이 있었는지"를 보여줘야 하는 곳에서는 이 함수를 쓴다.
    """

    row = conn.execute(
        "SELECT * FROM deploy_runs WHERE project_id = ? AND pr_url IS NOT NULL "
        "ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return DeployRun.from_row(row) if row else None


def upsert_tracking_config(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ga4_account_id: str | None = None,
    ga4_property_id: str | None = None,
    ga4_measurement_id: str | None = None,
    ga4_stream_id: str | None = None,
    gtm_account_id: str | None = None,
    gtm_container_id: str | None = None,
    gtm_workspace_id: str | None = None,
    gtm_last_published_version: str | None = None,
    ads_customer_id: str | None = None,
    ads_conversion_action_ids: str | None = None,
) -> TrackingConfig:
    """project_id 기준 1:1 upsert. None으로 넘긴 필드는 기존 값을 덮어쓰지 않는다.

    ads_conversion_action_ids는 JSON 배열 문자열 전체를 교체한다 — 기존 목록에 추가하려면
    호출자가 get_tracking_config()로 읽은 뒤 합쳐서 넘겨야 한다.
    """

    now = _now()
    conn.execute(
        """
        INSERT INTO tracking_configs (
            project_id, ga4_account_id, ga4_property_id, ga4_measurement_id, ga4_stream_id,
            gtm_account_id, gtm_container_id, gtm_workspace_id, gtm_last_published_version,
            ads_customer_id, ads_conversion_action_ids, last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, '[]'), ?)
        ON CONFLICT(project_id) DO UPDATE SET
            ga4_account_id = COALESCE(excluded.ga4_account_id, tracking_configs.ga4_account_id),
            ga4_property_id = COALESCE(excluded.ga4_property_id, tracking_configs.ga4_property_id),
            ga4_measurement_id = COALESCE(excluded.ga4_measurement_id, tracking_configs.ga4_measurement_id),
            ga4_stream_id = COALESCE(excluded.ga4_stream_id, tracking_configs.ga4_stream_id),
            gtm_account_id = COALESCE(excluded.gtm_account_id, tracking_configs.gtm_account_id),
            gtm_container_id = COALESCE(excluded.gtm_container_id, tracking_configs.gtm_container_id),
            gtm_workspace_id = COALESCE(excluded.gtm_workspace_id, tracking_configs.gtm_workspace_id),
            gtm_last_published_version = COALESCE(
                excluded.gtm_last_published_version, tracking_configs.gtm_last_published_version
            ),
            ads_customer_id = COALESCE(excluded.ads_customer_id, tracking_configs.ads_customer_id),
            ads_conversion_action_ids = CASE
                WHEN ? IS NULL THEN tracking_configs.ads_conversion_action_ids
                ELSE excluded.ads_conversion_action_ids
            END,
            last_synced_at = excluded.last_synced_at
        """,
        (
            project_id,
            ga4_account_id,
            ga4_property_id,
            ga4_measurement_id,
            ga4_stream_id,
            gtm_account_id,
            gtm_container_id,
            gtm_workspace_id,
            gtm_last_published_version,
            ads_customer_id,
            ads_conversion_action_ids,
            now,
            ads_conversion_action_ids,
        ),
    )
    conn.commit()
    return get_tracking_config(conn, project_id)  # type: ignore[return-value]


def get_tracking_config(conn: sqlite3.Connection, project_id: int) -> TrackingConfig | None:
    row = conn.execute(
        "SELECT * FROM tracking_configs WHERE project_id = ?", (project_id,)
    ).fetchone()
    return TrackingConfig.from_row(row) if row else None
