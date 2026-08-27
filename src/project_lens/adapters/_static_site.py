"""여러 배포 어댑터(Cloudflare Workers, Vercel, GitHub Pages)가 공유하는 정적 사이트
GTM 삽입 전략.

배포 방식(어디에 올라가는가)과 프레임워크(무엇으로 만들었는가)는 서로 다른 축이다 —
Cloudflare Workers든 Vercel이든 GitHub Pages든, 소스가 순수 정적 HTML이면 같은 방식으로
삽입하면 되고 Docusaurus/Astro Starlight면 각 프레임워크의 공식 설정 방식을 쓰면 된다.
그래서 "배포 방식을 감지해 프로젝트 루트를 찾는 것"만 각 어댑터의 책임으로 두고, 루트를
찾은 뒤 실제로 무엇을 어떻게 고칠지는 여기 한 곳에 모아 중복을 없앤다.
"""

from __future__ import annotations

import re
from pathlib import Path

from project_lens.adapters.base import ChangeSet

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


def inject_static_site_tracking(
    repo_path: Path, project_root: Path, gtm_id: str
) -> ChangeSet | None:
    """project_root에서 알려진 프레임워크 관례를 순서대로 시도한다.

    Docusaurus → Astro Starlight → 정적 HTML 순. 어느 것도 못 찾으면 None —
    호출자가 이슈 생성 폴백을 쓰도록 한다.
    """

    docusaurus_config = _find_docusaurus_config(project_root)
    if docusaurus_config is not None:
        return _inject_docusaurus(repo_path, docusaurus_config, gtm_id)

    starlight_config = _find_starlight_config(project_root)
    if starlight_config is not None:
        return _inject_starlight(repo_path, starlight_config, gtm_id)

    return _inject_html(repo_path, project_root, gtm_id)


def _inject_html(repo_path: Path, project_root: Path, gtm_id: str) -> ChangeSet | None:
    html_path = _find_html_entry(project_root)
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


def _inject_docusaurus(repo_path: Path, config_path: Path, gtm_id: str) -> ChangeSet | None:
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


def _inject_starlight(repo_path: Path, config_path: Path, gtm_id: str) -> ChangeSet | None:
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


def _find_html_entry(project_root: Path) -> Path | None:
    for candidate in _HTML_ENTRY_CANDIDATES:
        path = project_root / candidate
        if path.exists():
            return path
    return None


def _find_docusaurus_config(project_root: Path) -> Path | None:
    for candidate in _DOCUSAURUS_CONFIG_CANDIDATES:
        path = project_root / candidate
        if path.exists():
            return path
    return None


def _find_starlight_config(project_root: Path) -> Path | None:
    for candidate in _ASTRO_CONFIG_CANDIDATES:
        path = project_root / candidate
        if path.exists() and "starlight(" in path.read_text(encoding="utf-8"):
            return path
    return None
