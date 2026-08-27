from __future__ import annotations

import json

from project_lens.settings import AccountProfile, Settings, load_settings, save_settings


def test_default_settings_has_one_default_profile(lens_home):
    settings = Settings()
    assert settings.default_profile == "default"
    assert settings.profiles.keys() == {"default"}
    assert settings.org_profile_map == {}


def test_load_settings_returns_defaults_when_file_missing(lens_home):
    settings = load_settings()
    assert settings.profiles["default"] == AccountProfile()


def test_save_and_load_round_trip(lens_home):
    settings = Settings()
    settings.get_or_create_profile("lab").ga4_account_id = "999"
    settings.profiles["default"].ga4_account_id = "111"
    settings.org_profile_map["kokoa-lab"] = "lab"
    save_settings(settings)

    loaded = load_settings()
    assert loaded.profiles["default"].ga4_account_id == "111"
    assert loaded.profiles["lab"].ga4_account_id == "999"
    assert loaded.org_profile_map == {"kokoa-lab": "lab"}


def test_profile_for_org_falls_back_to_default(lens_home):
    settings = Settings()
    settings.profiles["default"].ga4_account_id = "111"
    settings.get_or_create_profile("lab").ga4_account_id = "999"
    settings.org_profile_map["kokoa-lab"] = "lab"

    assert settings.profile_for_org("kokoa-lab").ga4_account_id == "999"
    assert settings.profile_for_org("shinkeonkim").ga4_account_id == "111"
    assert settings.profile_for_org("unmapped-org").ga4_account_id == "111"


def test_load_settings_migrates_legacy_flat_schema(lens_home):
    from project_lens.settings import _settings_path

    legacy = {
        "ga4_account_id": "111",
        "gtm_account_id": "222",
        "ads_login_customer_id": "333",
    }
    _settings_path().write_text(json.dumps(legacy), encoding="utf-8")

    settings = load_settings()

    default = settings.profiles["default"]
    assert default.ga4_account_id == "111"
    assert default.gtm_account_id == "222"
    assert default.ads_login_customer_id == "333"


def test_get_or_create_profile_returns_existing(lens_home):
    settings = Settings()
    first = settings.get_or_create_profile("lab")
    first.ga4_account_id = "999"
    second = settings.get_or_create_profile("lab")
    assert second is first
    assert second.ga4_account_id == "999"
