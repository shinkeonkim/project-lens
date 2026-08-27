"""GA4/GTM/Ads 계정 ID 같은 비밀이 아닌 로컬 설정.

credentials_dir()와 달리 여기 값은 비밀이 아니라 "어떤 계정을 쓸지"에 대한 사용자
선택일 뿐이다. ~/.project-lens/settings.json에 평문으로 저장한다.

여러 GA4/Ads 계정(예: 개인용 vs 스터디 랩용)을 구분해 쓸 수 있도록 "프로필" 단위로
관리한다 — GitHub org(`kokoa-lab`, `shinkeonkim` 등)마다 다른 프로필을 매핑할 수 있고,
매핑이 없으면 `default_profile`을 쓴다. 프로필이 하나뿐이면(가장 흔한 경우) 사실상
이전 버전의 "전역 계정 하나" 방식과 동일하게 동작한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from project_lens.config import home_dir

_DEFAULT_PROFILE = "default"


@dataclass
class AccountProfile:
    ga4_account_id: str | None = None
    gtm_account_id: str | None = None
    ads_login_customer_id: str | None = None


@dataclass
class Settings:
    default_profile: str = _DEFAULT_PROFILE
    profiles: dict[str, AccountProfile] = field(
        default_factory=lambda: {_DEFAULT_PROFILE: AccountProfile()}
    )
    # github_org -> profile 이름. 없는 org는 default_profile을 쓴다.
    org_profile_map: dict[str, str] = field(default_factory=dict)

    def profile_for_org(self, github_org: str) -> AccountProfile:
        name = self.org_profile_map.get(github_org, self.default_profile)
        return self.profiles.get(name, AccountProfile())

    def get_or_create_profile(self, name: str) -> AccountProfile:
        if name not in self.profiles:
            self.profiles[name] = AccountProfile()
        return self.profiles[name]


def _settings_path() -> Path:
    return home_dir() / "settings.json"


def load_settings() -> Settings:
    path = _settings_path()
    if not path.exists():
        return Settings()

    data = json.loads(path.read_text(encoding="utf-8"))

    if "profiles" not in data:
        # 이전 버전(계정 하나만 저장하던 평평한 구조)과의 호환 — default 프로필로 승격.
        legacy_profile = AccountProfile(
            ga4_account_id=data.get("ga4_account_id"),
            gtm_account_id=data.get("gtm_account_id"),
            ads_login_customer_id=data.get("ads_login_customer_id"),
        )
        return Settings(profiles={_DEFAULT_PROFILE: legacy_profile})

    profiles = {name: AccountProfile(**p) for name, p in data["profiles"].items()}
    return Settings(
        default_profile=data.get("default_profile", _DEFAULT_PROFILE),
        profiles=profiles or {_DEFAULT_PROFILE: AccountProfile()},
        org_profile_map=data.get("org_profile_map", {}),
    )


def save_settings(settings: Settings) -> None:
    payload = {
        "default_profile": settings.default_profile,
        "profiles": {name: asdict(profile) for name, profile in settings.profiles.items()},
        "org_profile_map": settings.org_profile_map,
    }
    _settings_path().write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
