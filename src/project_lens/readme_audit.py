"""등록된 프로젝트들의 README.md 상태를 점검한다.

실제로 이 세션에서 `qr-gen`의 README가 `sv create` 스캐폴드 기본값 그대로 남아있는
걸 발견했었다 — 존재는 하지만 그 프로젝트에 대해 아무 정보도 없는 상태. 그래서
"있다/없다"만으로는 부족하고, 흔한 스캐폴드 기본 문구를 아는 것도 필요하다.
"""

from __future__ import annotations

from dataclasses import dataclass

_THIN_LENGTH_THRESHOLD = 300

# 실제로 마주친 것 위주 — 필요할 때마다 추가한다. 소문자로 비교한다.
_SCAFFOLD_MARKERS = (
    "everything you need to build a svelte project",  # sv create (qr-gen에서 실제로 발견)
    "getting started with create react app",
    "this project was bootstrapped with create-vite",
    "# vue 3 + typescript + vite",
    "django administration",
)


@dataclass(frozen=True)
class ReadmeStatus:
    slug: str
    github_url: str
    verdict: str  # "missing" | "template" | "thin" | "ok"
    length: int


def classify_readme(content: str | None) -> str:
    if content is None or not content.strip():
        return "missing"

    normalized = content.strip().lower()
    if any(marker in normalized for marker in _SCAFFOLD_MARKERS):
        return "template"

    if len(content.strip()) < _THIN_LENGTH_THRESHOLD:
        return "thin"

    return "ok"


_VERDICT_LABELS = {
    "missing": "README 없음",
    "template": "스캐폴드 기본값 그대로",
    "thin": "내용 부족",
    "ok": "양호",
}


def verdict_label(verdict: str) -> str:
    return _VERDICT_LABELS.get(verdict, verdict)
