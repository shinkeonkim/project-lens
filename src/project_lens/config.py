"""project-lens의 로컬 상태 경로 관리.

DB/로그/자격증명은 항상 이 저장소 바깥, 사용자 홈 디렉터리 아래에 둔다
(docs/ARCHITECTURE.md, docs/SECURITY.md 참고). 테스트에서는
PROJECT_LENS_HOME 환경변수로 임시 경로를 주입한다.
"""

from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    override = os.environ.get("PROJECT_LENS_HOME")
    base = Path(override) if override else Path.home() / ".project-lens"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return home_dir() / "registry.sqlite3"


def logs_dir() -> Path:
    path = home_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def credentials_dir() -> Path:
    path = home_dir() / "credentials"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def workspace_dir() -> Path:
    path = home_dir() / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir() -> Path:
    path = home_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def dashboard_path() -> Path:
    return home_dir() / "dashboard.html"
