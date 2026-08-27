"""gh CLI를 감싸는 얇은 래퍼.

project-lens는 자체 GitHub 토큰을 발급/저장하지 않고, 로컬에 이미 로그인된
`gh auth` 세션을 그대로 재사용한다 (docs/SECURITY.md).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from project_lens.errors import AuthError, RepoAccessError, ValidationError

_URL_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)"
    r"(?P<org>[A-Za-z0-9._-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)

_REPO_VIEW_FIELDS = "nameWithOwner,owner,name,url,visibility,isPrivate,defaultBranchRef"


@dataclass(frozen=True)
class RepoInfo:
    org: str
    repo: str
    url: str
    visibility: str  # "public" | "private"
    default_branch: str


def parse_github_url(url: str) -> tuple[str, str]:
    match = _URL_RE.match(url.strip())
    if not match:
        raise ValidationError(
            f"GitHub 레포 URL 형식이 아닙니다: {url!r} "
            "(예: https://github.com/org/repo)"
        )
    return match.group("org"), match.group("repo")


def ensure_authenticated() -> None:
    result = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AuthError(
            "gh CLI가 로그인되어 있지 않습니다. `gh auth login`을 먼저 실행하세요.\n"
            f"{result.stderr.strip()}"
        )


def view_repo(url: str) -> RepoInfo:
    """레포 존재/접근 가능 여부를 확인하고 메타데이터를 반환한다.

    접근 불가(비공개+권한 없음, 존재하지 않음 등)면 RepoAccessError를 던진다.
    """

    org, repo = parse_github_url(url)
    result = subprocess.run(
        ["gh", "repo", "view", url, "--json", _REPO_VIEW_FIELDS],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RepoAccessError(
            f"{org}/{repo}에 접근할 수 없습니다. 저장소가 존재하지 않거나 "
            "접근 권한이 없을 수 있습니다 (private 조직이면 `gh auth status`의 "
            "조직 접근 권한을 확인하세요).\n"
            f"{result.stderr.strip()}"
        )

    data = json.loads(result.stdout)
    default_branch = (data.get("defaultBranchRef") or {}).get("name", "")
    return RepoInfo(
        org=data["owner"]["login"],
        repo=data["name"],
        url=data["url"],
        visibility="private" if data.get("isPrivate") else "public",
        default_branch=default_branch,
    )


def pr_state(pr_url: str) -> str | None:
    """PR_URL의 상태(OPEN/MERGED/CLOSED)를 조회한다. 실패하면 None(대시보드 등에서

    조회 하나 실패했다고 전체를 실패시키지 않기 위해 예외 대신 None을 씀)."""

    result = subprocess.run(
        ["gh", "pr", "view", pr_url, "--json", "state"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)["state"]
    except (json.JSONDecodeError, KeyError):
        return None


def clone_repo(github_url: str, dest: Path) -> None:
    """github_url을 dest 경로로 clone한다. dest는 호출 전 존재하지 않아야 한다."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "repo", "clone", github_url, str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RepoAccessError(f"clone 실패: {github_url}\n{result.stderr.strip()}")
