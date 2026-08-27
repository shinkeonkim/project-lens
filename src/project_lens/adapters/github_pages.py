"""GitHub Pages 배포 어댑터 (docs/ADAPTERS.md).

현재 등록된 14개 프로젝트 중 GitHub Pages로 배포되는 건 없다 — Vercel 어댑터와 같은
이유(사용자 요청, Phase 6)로 미리 만들어 둔다. GitHub Pages는 wrangler.toml 같은
단일 설정 파일 관례가 없어서 두 신호를 함께 본다: `.github/workflows/*.yml`이 Pages
배포 액션(`actions/deploy-pages`, `peaceiris/actions-gh-pages`)을 쓰는지, 또는
커스텀 도메인을 쓸 때 생기는 `CNAME` 파일이 있는지. 콘텐츠 루트는 레포 루트 또는
`docs/`(Pages의 흔한 소스 디렉터리 설정) 순으로 시도한다.

실제 삽입은 다른 정적 배포 어댑터와 같은 공유 로직(`adapters/_static_site.py`)을 쓴다.
"""

from __future__ import annotations

from pathlib import Path

from project_lens.adapters._static_site import inject_static_site_tracking
from project_lens.adapters.base import ChangeSet

_DEPLOY_PAGES_MARKERS = ("actions/deploy-pages", "peaceiris/actions-gh-pages")
_CONTENT_ROOT_CANDIDATES = (".", "docs")


class GitHubPagesAdapter:
    name = "github_pages"

    def detect(self, repo_path: Path) -> bool:
        return self._looks_like_pages_repo(repo_path)

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        if not self._looks_like_pages_repo(repo_path):
            return None

        for rel in _CONTENT_ROOT_CANDIDATES:
            candidate = repo_path / rel
            if not candidate.is_dir():
                continue
            result = inject_static_site_tracking(repo_path, candidate, gtm_id)
            if result is not None:
                return result

        return None

    def _looks_like_pages_repo(self, repo_path: Path) -> bool:
        if (repo_path / "CNAME").exists() or (repo_path / "docs" / "CNAME").exists():
            return True
        return self._uses_pages_deploy_workflow(repo_path)

    def _uses_pages_deploy_workflow(self, repo_path: Path) -> bool:
        workflows_dir = repo_path / ".github" / "workflows"
        if not workflows_dir.is_dir():
            return False

        for path in workflows_dir.iterdir():
            if path.suffix not in (".yml", ".yaml"):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(marker in content for marker in _DEPLOY_PAGES_MARKERS):
                return True

        return False
