"""Cloudflare Workers 배포 어댑터 (docs/ADAPTERS.md).

이 파일의 책임은 "wrangler 프로젝트를 찾는 것"뿐이다. 찾은 뒤 실제로 무엇을 어떻게
고칠지(정적 HTML / Docusaurus / Astro Starlight)는 `adapters/_static_site.py`에
공유 로직으로 있다 — Vercel/GitHub Pages 어댑터도 같은 걸 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_lens.adapters._static_site import inject_static_site_tracking
from project_lens.adapters.base import ChangeSet

_WRANGLER_FILENAMES = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")


class CloudflareWorkersAdapter:
    name = "cloudflare_workers"

    def detect(self, repo_path: Path) -> bool:
        return self._find_wrangler_project_root(repo_path) is not None

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        project_root = self._find_wrangler_project_root(repo_path)
        if project_root is None:
            return None
        return inject_static_site_tracking(repo_path, project_root, gtm_id)

    def _find_wrangler_project_root(self, repo_path: Path) -> Path | None:
        candidates = [repo_path] + sorted(
            p for p in repo_path.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
        for candidate in candidates:
            if any((candidate / name).exists() for name in _WRANGLER_FILENAMES):
                return candidate

            package_json = candidate / "package.json"
            if package_json.exists():
                try:
                    data = json.loads(package_json.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "wrangler" in deps:
                    return candidate

        return None
