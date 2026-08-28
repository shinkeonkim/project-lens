from __future__ import annotations

from project_lens.adapters._ads_txt import build_ads_txt_content, inject_ads_txt


def test_build_ads_txt_content_matches_iab_format():
    content = build_ads_txt_content("pub-1234567890123456")
    assert content == "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n"


def test_uses_existing_public_dir(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "package.json").write_text("{}")

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set is not None
    assert change_set.changed_files == ("public/ads.txt",)
    assert (tmp_path / "public" / "ads.txt").read_text() == "google.com, pub-123, DIRECT, f08c47fec0942fa0\n"


def test_uses_existing_static_dir_over_public_when_only_static_exists(tmp_path):
    (tmp_path / "static").mkdir()

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("static/ads.txt",)


def test_prefers_public_over_static_when_both_exist(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "static").mkdir()

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("public/ads.txt",)


def test_uses_monorepo_apps_web_public_when_present(tmp_path):
    (tmp_path / "apps" / "web" / "public").mkdir(parents=True)

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("apps/web/public/ads.txt",)


def test_creates_static_dir_for_sveltekit_when_none_exists(tmp_path):
    (tmp_path / "svelte.config.js").write_text("export default {}")

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("static/ads.txt",)
    assert (tmp_path / "static" / "ads.txt").exists()


def test_creates_public_dir_for_nextjs_monorepo_when_none_exists(tmp_path):
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "package.json").write_text("{}")

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("apps/web/public/ads.txt",)


def test_creates_public_dir_for_plain_package_json_project(tmp_path):
    (tmp_path / "package.json").write_text("{}")

    change_set = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert change_set.changed_files == ("public/ads.txt",)


def test_returns_none_when_no_signal_at_all(tmp_path):
    assert inject_ads_txt(tmp_path, tmp_path, "pub-123") is None


def test_is_idempotent_when_content_unchanged(tmp_path):
    (tmp_path / "public").mkdir()

    first = inject_ads_txt(tmp_path, tmp_path, "pub-123")
    second = inject_ads_txt(tmp_path, tmp_path, "pub-123")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_overwrites_when_publisher_id_changes(tmp_path):
    (tmp_path / "public").mkdir()

    inject_ads_txt(tmp_path, tmp_path, "pub-123")
    second = inject_ads_txt(tmp_path, tmp_path, "pub-456")

    assert second.already_present is False
    assert (tmp_path / "public" / "ads.txt").read_text() == "google.com, pub-456, DIRECT, f08c47fec0942fa0\n"
