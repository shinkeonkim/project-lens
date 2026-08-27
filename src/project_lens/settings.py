"""GA4/GTM 기본 계정 ID 같은 비밀이 아닌 로컬 설정.

credentials_dir()와 달리 여기 값은 비밀이 아니라 "어떤 계정을 기본으로 쓸지"에 대한
사용자 선택일 뿐이다. ~/.project-lens/settings.json에 평문으로 저장한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from project_lens.config import home_dir


@dataclass
class Settings:
    ga4_account_id: str | None = None
    gtm_account_id: str | None = None


def _settings_path() -> Path:
    return home_dir() / "settings.json"


def load_settings() -> Settings:
    path = _settings_path()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Settings(**data)


def save_settings(settings: Settings) -> None:
    _settings_path().write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
