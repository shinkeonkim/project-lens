"""AdSense용 ads.txt 배치 — _static_site.py의 GTM 삽입과 같은 원칙(배포 방식이
아니라 실제 프레임워크 구조를 보고 위치를 정한다)을 따르되, 이건 기존 파일을
patch하는 게 아니라 정적 파일 하나를 "빌드 시 그대로 루트에 복사되는 디렉터리"에
떨어뜨리는 것뿐이라 훨씬 단순하다.

ads.txt는 IAB 스펙상 호스트마다(서브도메인 포함) 자기 자리에 있어야 한다 — 부모
도메인의 것을 자동으로 상속하지 않는다. 그래서 광고를 붙이는 사이트마다 이 파일을
따로 배치해야 한다.
"""

from __future__ import annotations

from pathlib import Path

from project_lens.adapters.base import ChangeSet

_ADS_TXT_FILENAME = "ads.txt"

# 존재하면 그대로 쓰는 후보들 — 순서가 우선순위다.
_EXISTING_DIR_CANDIDATES = ("public", "static", "apps/web/public", "apps/web/static")

_SVELTEKIT_CONFIG_CANDIDATES = ("svelte.config.js", "svelte.config.ts")


def build_ads_txt_content(publisher_id: str) -> str:
    # 표준 한 줄 포맷 (https://support.google.com/adsense/answer/9394911).
    # "f08c47fec0942fa0"는 AdSense 전용 고정 값(Google의 IAB TAG-ID)이다.
    return f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0\n"


def inject_ads_txt(repo_path: Path, project_root: Path, publisher_id: str) -> ChangeSet | None:
    target_dir = _find_or_infer_public_dir(project_root)
    if target_dir is None:
        return None

    ads_txt_path = target_dir / _ADS_TXT_FILENAME
    content = build_ads_txt_content(publisher_id)
    rel_path = str(ads_txt_path.relative_to(repo_path))

    if ads_txt_path.exists() and ads_txt_path.read_text(encoding="utf-8").strip() == content.strip():
        return ChangeSet(changed_files=(), summary=f"{rel_path}에 이미 있습니다.", already_present=True)

    target_dir.mkdir(parents=True, exist_ok=True)
    ads_txt_path.write_text(content, encoding="utf-8")

    return ChangeSet(changed_files=(rel_path,), summary=f"{rel_path}를 추가했습니다.")


def _find_or_infer_public_dir(project_root: Path) -> Path | None:
    for candidate in _EXISTING_DIR_CANDIDATES:
        path = project_root / candidate
        if path.is_dir():
            return path

    # 존재하는 디렉터리가 없으면 프레임워크 관례로 새로 만들 위치를 정한다.
    if any((project_root / c).exists() for c in _SVELTEKIT_CONFIG_CANDIDATES):
        return project_root / "static"

    if (project_root / "apps" / "web").is_dir():
        return project_root / "apps" / "web" / "public"

    if (project_root / "package.json").exists():
        return project_root / "public"

    return None
