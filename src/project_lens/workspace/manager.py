"""'작업 시에만 clone, 끝나면 삭제' 원칙을 강제하는 Workspace Manager.

docs/ARCHITECTURE.md의 설계대로 성공/실패와 무관하게 try/finally로 임시 디렉터리를
정리한다. 디버깅 목적의 keep=True만 예외.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from project_lens.config import workspace_dir
from project_lens.github.client import clone_repo


@contextmanager
def cloned_workspace(
    slug: str, token: str, github_url: str, *, keep: bool = False
) -> Iterator[Path]:
    """github_url을 임시 디렉터리에 clone하고, 블록이 끝나면(예외 포함) 정리한다.

    token은 동시 실행 시 워크스페이스 경로가 겹치지 않도록 구분하는 값이다
    (실제 실행은 deploy_runs.id, dry-run은 임의의 고유 문자열).
    """

    path = workspace_dir() / f"{slug}-{token}"
    if path.exists():
        shutil.rmtree(path)
    try:
        clone_repo(github_url, path)
        yield path
    finally:
        if not keep and path.exists():
            shutil.rmtree(path, ignore_errors=True)
