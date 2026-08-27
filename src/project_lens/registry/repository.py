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
) -> TrackingConfig:
    """project_id 기준 1:1 upsert. None으로 넘긴 필드는 기존 값을 덮어쓰지 않는다."""

    now = _now()
    conn.execute(
        """
        INSERT INTO tracking_configs (
            project_id, ga4_account_id, ga4_property_id, ga4_measurement_id, ga4_stream_id,
            gtm_account_id, gtm_container_id, gtm_workspace_id, gtm_last_published_version,
            last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            now,
        ),
    )
    conn.commit()
    return get_tracking_config(conn, project_id)  # type: ignore[return-value]


def get_tracking_config(conn: sqlite3.Connection, project_id: int) -> TrackingConfig | None:
    row = conn.execute(
        "SELECT * FROM tracking_configs WHERE project_id = ?", (project_id,)
    ).fetchone()
    return TrackingConfig.from_row(row) if row else None
