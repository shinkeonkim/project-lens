"""Cloudflare Workers 배포 어댑터 (docs/ADAPTERS.md).

정적 HTML 엔트리 포인트에 GTM 스니펫을 삽입하는 것이 기본이다. 정적 사이트
생성기(Docusaurus classic preset, Astro Starlight)로 만든 사이트는 정적 HTML이
빌드 산출물일 뿐이라 소스에는 없으므로, 각자 공식 설정 방식(`googleTagManager`
프리셋 옵션, Starlight `head` 옵션)으로 따로 처리한다. wrangler 프로젝트가 레포
루트가 아니라 한 단계 아래 서브디렉터리에 있는 경우(모노레포 스타일)도 찾는다.
그 외 프레임워크 관례나 삽입 지점을 못 찾는 경우는 이후 Phase에서 확장한다 —
지금은 못 찾으면 None을 반환해 호출자가 이슈 생성 폴백을 쓰도록 한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from project_lens.adapters.base import ChangeSet

_WRANGLER_FILENAMES = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")
_HTML_ENTRY_CANDIDATES = ("index.html", "public/index.html", "src/index.html")
_DOCUSAURUS_CONFIG_CANDIDATES = ("docusaurus.config.ts", "docusaurus.config.js")
_ASTRO_CONFIG_CANDIDATES = ("astro.config.mjs", "astro.config.ts", "astro.config.js")

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

# Docusaurus의 create-docusaurus 기본 스캐폴드가 만드는 classic preset 모양
# (`presets: [['classic', { docs: {...}, ... }]]`)에 맞춘 앵커. 들여쓰기는
# docs: 줄의 들여쓰기를 그대로 읽어 맞춘다 — 2/4칸 어느 쪽이든 대응한다.
_DOCUSAURUS_PRESET_RE = re.compile(
    r"(['\"]classic['\"],\s*\n[ \t]*\{\s*\n)([ \t]*)(docs:\s*\{)"
)

# `starlight({ ... })` 통합 호출 바로 다음 줄의 들여쓰기를 읽어 그 안 첫 속성으로
# head 옵션을 끼워 넣는다. https://starlight.astro.build/reference/configuration/#head
_STARLIGHT_CALL_RE = re.compile(r"(starlight\(\{\s*\n)([ \t]*)")

_STARLIGHT_INLINE_SCRIPT = (
    "(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':"
    "new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],"
    "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src="
    "'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);"
    "}})(window,document,'script','dataLayer','{gtm_id}');"
)


class CloudflareWorkersAdapter:
    name = "cloudflare_workers"

    def detect(self, repo_path: Path) -> bool:
        return self._find_wrangler_project_root(repo_path) is not None

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        project_root = self._find_wrangler_project_root(repo_path)
        if project_root is None:
            return None

        docusaurus_config = self._find_docusaurus_config(project_root)
        if docusaurus_config is not None:
            return self._inject_docusaurus(repo_path, docusaurus_config, gtm_id)

        starlight_config = self._find_starlight_config(project_root)
        if starlight_config is not None:
            return self._inject_starlight(repo_path, starlight_config, gtm_id)

        return self._inject_html(repo_path, project_root, gtm_id)

    def _inject_html(self, repo_path: Path, project_root: Path, gtm_id: str) -> ChangeSet | None:
        html_path = self._find_html_entry(project_root)
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

    def _inject_docusaurus(
        self, repo_path: Path, config_path: Path, gtm_id: str
    ) -> ChangeSet | None:
        original = config_path.read_text(encoding="utf-8")
        rel_path = str(config_path.relative_to(repo_path))

        if "googleTagManager" in original:
            return ChangeSet(
                changed_files=(),
                summary=f"{rel_path}에 이미 googleTagManager 설정이 있습니다.",
                already_present=True,
            )

        match = _DOCUSAURUS_PRESET_RE.search(original)
        if not match:
            return None

        prefix, indent, docs_key = match.group(1), match.group(2), match.group(3)
        replacement = (
            f"{prefix}{indent}googleTagManager: {{\n"
            f'{indent}  containerId: "{gtm_id}",\n'
            f"{indent}}},\n"
            f"{indent}{docs_key}"
        )
        updated = original[: match.start()] + replacement + original[match.end() :]
        config_path.write_text(updated, encoding="utf-8")

        return ChangeSet(
            changed_files=(rel_path,),
            summary=f"{rel_path}에 Docusaurus googleTagManager({gtm_id}) 설정을 추가했습니다.",
        )

    def _inject_starlight(
        self, repo_path: Path, config_path: Path, gtm_id: str
    ) -> ChangeSet | None:
        original = config_path.read_text(encoding="utf-8")
        rel_path = str(config_path.relative_to(repo_path))

        if gtm_id in original:
            return ChangeSet(
                changed_files=(),
                summary=f"{rel_path}에 이미 {gtm_id}가 삽입되어 있습니다.",
                already_present=True,
            )

        match = _STARLIGHT_CALL_RE.search(original)
        if not match:
            return None

        prefix, indent = match.group(1), match.group(2)
        script = _STARLIGHT_INLINE_SCRIPT.format(gtm_id=gtm_id)
        replacement = (
            f"{prefix}{indent}head: [\n"
            f"{indent}  {{\n"
            f"{indent}    tag: 'script',\n"
            f"{indent}    content: `{script}`,\n"
            f"{indent}  }},\n"
            f"{indent}],\n"
            f"{indent}"
        )
        updated = original[: match.start()] + replacement + original[match.end() :]
        config_path.write_text(updated, encoding="utf-8")

        return ChangeSet(
            changed_files=(rel_path,),
            summary=f"{rel_path}에 Starlight head 옵션으로 GTM({gtm_id}) 스크립트를 추가했습니다.",
        )

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

    def _find_html_entry(self, project_root: Path) -> Path | None:
        for candidate in _HTML_ENTRY_CANDIDATES:
            path = project_root / candidate
            if path.exists():
                return path
        return None

    def _find_docusaurus_config(self, project_root: Path) -> Path | None:
        for candidate in _DOCUSAURUS_CONFIG_CANDIDATES:
            path = project_root / candidate
            if path.exists():
                return path
        return None

    def _find_starlight_config(self, project_root: Path) -> Path | None:
        for candidate in _ASTRO_CONFIG_CANDIDATES:
            path = project_root / candidate
            if path.exists() and "starlight(" in path.read_text(encoding="utf-8"):
                return path
        return None
