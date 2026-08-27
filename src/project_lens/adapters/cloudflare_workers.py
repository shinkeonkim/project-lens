"""Cloudflare Workers 배포 어댑터 (docs/ADAPTERS.md).

Phase 1 범위: 정적 HTML 엔트리 포인트에 GTM 스니펫을 삽입한다. 프레임워크(Next.js 등)
관례 삽입이나, HTML 엔트리를 못 찾는 경우의 코드 생성 삽입은 이후 Phase에서 확장한다 —
지금은 못 찾으면 None을 반환해 호출자가 이슈 생성 폴백을 쓰도록 한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from project_lens.adapters.base import ChangeSet

_HTML_ENTRY_CANDIDATES = ("index.html", "public/index.html", "src/index.html")

_HEAD_RE = re.compile(r"<head[^>]*>", re.IGNORECASE)
_BODY_RE = re.compile(r"<body[^>]*>", re.IGNORECASE)

_HEAD_SNIPPET = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
<!-- End Google Tag Manager -->
"""

_BODY_SNIPPET = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
"""


class CloudflareWorkersAdapter:
    name = "cloudflare_workers"

    def detect(self, repo_path: Path) -> bool:
        if (repo_path / "wrangler.toml").exists():
            return True
        if (repo_path / "wrangler.jsonc").exists() or (repo_path / "wrangler.json").exists():
            return True

        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "wrangler" in deps:
                return True

        return False

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        html_path = self._find_html_entry(repo_path)
        if html_path is None:
            return None

        original = html_path.read_text(encoding="utf-8")
        rel_path = str(html_path.relative_to(repo_path))

        if gtm_id in original:
            return ChangeSet(
                changed_files=(),
                summary=f"{rel_path}에 이미 {gtm_id}가 삽입되어 있습니다.",
                already_present=True,
            )

        body_match = _BODY_RE.search(original)
        head_match = _HEAD_RE.search(original)
        if not body_match or not head_match:
            return None

        # body 스니펫을 먼저 삽입해야 head 삽입으로 생기는 오프셋 변화의 영향을 받지 않는다.
        updated = (
            original[: body_match.end()]
            + "\n"
            + _BODY_SNIPPET.format(gtm_id=gtm_id)
            + original[body_match.end() :]
        )
        head_match = _HEAD_RE.search(updated)
        assert head_match is not None  # head는 body보다 앞에 있으므로 오프셋 영향 없음
        updated = (
            updated[: head_match.end()]
            + "\n"
            + _HEAD_SNIPPET.format(gtm_id=gtm_id)
            + updated[head_match.end() :]
        )

        html_path.write_text(updated, encoding="utf-8")

        return ChangeSet(
            changed_files=(rel_path,),
            summary=f"{rel_path}에 GTM({gtm_id}) 스니펫을 삽입했습니다.",
        )

    def _find_html_entry(self, repo_path: Path) -> Path | None:
        for candidate in _HTML_ENTRY_CANDIDATES:
            path = repo_path / candidate
            if path.exists():
                return path
        return None
