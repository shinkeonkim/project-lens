"""대시보드에 필요한 데이터를 레지스트리 + (가능하면) 실시간 API에서 모은다.

프로젝트 수가 늘어날수록(현재 27개) `lens dashboard`가 느려지는 문제가 있었다 —
프로젝트마다 `gh pr view`(서브프로세스)와 GA4 리포트 API 호출을 순서대로
기다렸기 때문이다. SQLite 조회는 로컬이라 빠르니 그대로 순차 처리하고, 느린
I/O(gh 서브프로세스 + GA4 API)만 스레드 풀로 병렬화한다 — sqlite3 커넥션은
스레드 안전하지 않으므로 병렬 구간에서는 절대 건드리지 않는다.
"""

from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# gRPC(GA4 클라이언트)가 여러 스레드에서 동시에 fork-safety 관련 INFO 로그
# ("Other threads are currently calling into gRPC, skipping fork() handlers")를
# 쏟아내는데, 병렬 조회 자체는 정상 동작이라 무해하다 — 콘솔만 지저분해지므로
# import 시점에 조용히 시킨다. 이미 다른 값으로 설정돼 있으면 존중한다.
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")

from project_lens.dashboard import DashboardRow
from project_lens.github.client import pr_state
from project_lens.google import ga4_reporting
from project_lens.google.auth import load_credentials
from project_lens.health import check_site_health
from project_lens.registry.models import Project, TrackingConfig
from project_lens.registry.repository import get_latest_pr_run, get_latest_run, get_tracking_config, list_projects

_MAX_WORKERS = 8


@dataclass
class _ProjectSnapshot:
    project: Project
    tracking: TrackingConfig | None
    run_status: str | None
    run_summary: str | None
    pr_url: str | None


def collect_dashboard_rows(conn: sqlite3.Connection, *, offline: bool) -> list[DashboardRow]:
    """모든 등록된 프로젝트의 DashboardRow를 만든다.

    1단계(SQLite, 순차): 프로젝트/트래킹/최근 run 정보를 읽는다 — 로컬이라 빠르다.
    2단계(네트워크, 병렬): PR 상태(gh CLI)와 GA4 7일 리포트를 스레드 풀로 동시에
    가져온다 — 커넥션을 스레드에 넘기지 않는다.
    """

    snapshots: list[_ProjectSnapshot] = []
    for proj in list_projects(conn):
        tracking = get_tracking_config(conn, proj.id)
        latest_run = get_latest_run(conn, proj.id)
        latest_pr_run = get_latest_pr_run(conn, proj.id)
        snapshots.append(
            _ProjectSnapshot(
                project=proj,
                tracking=tracking,
                run_status=latest_run.status if latest_run else None,
                run_summary=latest_run.summary if latest_run else None,
                pr_url=latest_pr_run.pr_url if latest_pr_run else None,
            )
        )

    data_client = None if offline else _try_build_ga4_client()

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        rows = list(pool.map(lambda s: _build_row(s, data_client), snapshots))

    return rows


def _try_build_ga4_client():
    try:
        return ga4_reporting.build_client(load_credentials())
    except Exception:
        return None  # 대시보드는 인증 실패로도 멈추면 안 된다 — GA4 수치만 비운다


def _build_row(snapshot: _ProjectSnapshot, data_client) -> DashboardRow:
    proj = snapshot.project
    tracking = snapshot.tracking

    pr_state_value = pr_state(snapshot.pr_url) if snapshot.pr_url else None
    site_health = check_site_health(proj.site_url)

    gtm_console_url = None
    if tracking and tracking.gtm_account_id and tracking.gtm_container_id:
        gtm_console_url = (
            "https://tagmanager.google.com/#/container/accounts/"
            f"{tracking.gtm_account_id}/containers/{tracking.gtm_container_id}/workspaces"
        )

    ga4_active_users = None
    ga4_sessions = None
    if data_client is not None and tracking and tracking.ga4_property_id:
        try:
            summary = ga4_reporting.run_summary_report(
                data_client, property_id=tracking.ga4_property_id, start_date="7daysAgo"
            )
            ga4_active_users = summary.active_users
            ga4_sessions = summary.sessions
        except Exception:
            pass  # 이 프로젝트의 GA4 수치만 비운다 — 대시보드 전체를 실패시키지 않는다

    return DashboardRow(
        slug=proj.slug,
        github_url=proj.github_url,
        site_url=proj.site_url,
        status=proj.status,
        deployment_type=proj.deployment_type,
        pr_url=snapshot.pr_url,
        pr_state=pr_state_value,
        run_status=snapshot.run_status,
        run_summary=snapshot.run_summary,
        ga4_measurement_id=tracking.ga4_measurement_id if tracking else None,
        gtm_console_url=gtm_console_url,
        ga4_active_users_7d=ga4_active_users,
        ga4_sessions_7d=ga4_sessions,
        site_health_status=site_health.status,
        site_health_detail=site_health.detail,
    )
