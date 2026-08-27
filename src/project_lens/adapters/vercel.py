"""Vercel 배포 어댑터 (docs/ADAPTERS.md).

현재 등록된 14개 프로젝트 중 Vercel로 배포되는 건 없다 — 신규 프로젝트가 생길 때를
대비해 만들어 둔다(사용자 요청, Phase 6). detect()가 vercel.json 또는 package.json의
`vercel` 의존성으로 프로젝트를 찾으면, 실제 삽입은 CloudflareWorkersAdapter와 같은
공유 로직(`adapters/_static_site.py`)을 쓴다 — 배포 대상이 어디든 소스가 정적
HTML/Docusaurus/Astro Starlight면 삽입 방식은 같기 때문이다.

Next.js처럼 빌드 시점에 값이 굳는 프레임워크는(코드/CI까지 손대야 함) 일반화하기보다
`OhMyHomelabAdapter`가 `codekr`에 한 것처럼 실제 대상 레포가 생겼을 때 그 레포 구조에
맞춰 전용으로 만든다 — 검증할 실제 레포 없이 규칙을 추측해서 만들지 않는다
(`docs/ADAPTERS.md`의 "새 어댑터 추가 시 체크리스트" 참고).
"""

from __future__ import annotations

import json
from pathlib import Path

from project_lens.adapters._static_site import inject_static_site_tracking
from project_lens.adapters.base import ChangeSet

_VERCEL_CONFIG_FILENAMES = ("vercel.json",)


class VercelAdapter:
    name = "vercel"

    def detect(self, repo_path: Path) -> bool:
        return self._find_vercel_project_root(repo_path) is not None

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        project_root = self._find_vercel_project_root(repo_path)
        if project_root is None:
            return None
        return inject_static_site_tracking(repo_path, project_root, gtm_id)

    def _find_vercel_project_root(self, repo_path: Path) -> Path | None:
        candidates = [repo_path] + sorted(
            p for p in repo_path.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
        for candidate in candidates:
            if any((candidate / name).exists() for name in _VERCEL_CONFIG_FILENAMES):
                return candidate

            package_json = candidate / "package.json"
            if package_json.exists():
                try:
                    data = json.loads(package_json.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "vercel" in deps:
                    return candidate

        return None
