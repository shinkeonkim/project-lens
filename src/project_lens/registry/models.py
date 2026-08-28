from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    id: int
    slug: str
    name: str
    github_url: str
    github_org: str
    github_repo: str
    visibility: str
    default_branch: str
    deployment_type: str
    deploy_mode: str
    status: str
    notes: str
    created_at: str
    updated_at: str
    site_url: str | None = None
    ads_policy: str = "unreviewed"  # "allowed" | "excluded" | "unreviewed"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Project":
        return cls(**{key: row[key] for key in row.keys()})


@dataclass(frozen=True)
class DeployRun:
    id: int
    project_id: int
    run_type: str
    status: str
    started_at: str
    finished_at: str | None
    commit_sha: str | None
    pr_url: str | None
    summary: str | None
    error_code: str | None
    error_summary: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "DeployRun":
        return cls(**{key: row[key] for key in row.keys()})


@dataclass(frozen=True)
class TrackingConfig:
    id: int
    project_id: int
    ga4_account_id: str | None
    ga4_property_id: str | None
    ga4_measurement_id: str | None
    ga4_stream_id: str | None
    gtm_account_id: str | None
    gtm_container_id: str | None
    gtm_workspace_id: str | None
    gtm_last_published_version: str | None
    ads_customer_id: str | None
    ads_conversion_action_ids: str
    config_version: int
    last_synced_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TrackingConfig":
        return cls(**{key: row[key] for key in row.keys()})
