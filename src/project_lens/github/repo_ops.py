"""clone된 로컬 레포에 대한 git/gh 오퍼레이션 (브랜치/커밋/push/PR/이슈).

읽기 전용 메타데이터 조회는 client.py, 여기는 상태를 변경하는 오퍼레이션만 다룬다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_lens.errors import DeployError


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def create_branch(repo_path: Path, branch: str) -> None:
    result = _run(["git", "checkout", "-b", branch], repo_path)
    if result.returncode != 0:
        raise DeployError(f"브랜치 생성 실패({branch}): {result.stderr.strip()}")


def commit_all(repo_path: Path, message: str) -> str:
    _run(["git", "add", "-A"], repo_path)
    result = _run(["git", "commit", "-m", message], repo_path)
    if result.returncode != 0:
        raise DeployError(f"커밋 실패: {result.stderr.strip()}")

    sha_result = _run(["git", "rev-parse", "HEAD"], repo_path)
    return sha_result.stdout.strip()


def push_branch(repo_path: Path, branch: str) -> None:
    result = _run(["git", "push", "-u", "origin", branch], repo_path)
    if result.returncode != 0:
        raise DeployError(f"push 실패({branch}): {result.stderr.strip()}")


def create_pull_request(repo_path: Path, *, title: str, body: str, base: str) -> str:
    result = _run(
        ["gh", "pr", "create", "--title", title, "--body", body, "--base", base],
        repo_path,
    )
    if result.returncode != 0:
        raise DeployError(f"PR 생성 실패: {result.stderr.strip()}")

    return _last_url_line(result.stdout)


def create_issue(repo_path: Path, *, title: str, body: str) -> str:
    result = _run(["gh", "issue", "create", "--title", title, "--body", body], repo_path)
    if result.returncode != 0:
        raise DeployError(f"이슈 생성 실패: {result.stderr.strip()}")

    return _last_url_line(result.stdout)


def _last_url_line(stdout: str) -> str:
    lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise DeployError("gh 명령이 URL을 반환하지 않았습니다.")
    return lines[-1]
