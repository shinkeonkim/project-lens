"""docs/ARCHITECTURE.md의 Deployment Adapter 공통 계약.

어댑터는 git 오퍼레이션을 직접 하지 않는다 — 로컬 clone의 파일만 수정하고
ChangeSet을 반환하면, 실제 커밋/push/PR은 상위 CLI 레이어(github/repo_ops.py)가 수행한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ChangeSet:
    changed_files: tuple[str, ...]
    summary: str
    already_present: bool = False


class DeploymentAdapter(Protocol):
    name: str

    def detect(self, repo_path: Path) -> bool: ...

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        """트래킹 스니펫을 로컬 clone에 삽입한다.

        삽입 지점을 자동으로 특정할 수 없으면 None을 반환한다 — 호출자는 이를
        "이슈 생성" 폴백 신호로 처리해야 한다 (docs/ADAPTERS.md).
        """
        ...
