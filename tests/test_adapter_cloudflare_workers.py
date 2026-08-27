from __future__ import annotations

import json

from project_lens.adapters.cloudflare_workers import CloudflareWorkersAdapter

SAMPLE_HTML = """<!doctype html>
<html>
<head>
<title>dice-art</title>
</head>
<body>
<div id="app"></div>
</body>
</html>
"""


def test_detect_wrangler_toml(tmp_path):
    (tmp_path / "wrangler.toml").write_text("name = \"dice-art\"\n")
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_wrangler_jsonc(tmp_path):
    (tmp_path / "wrangler.jsonc").write_text("{}\n")
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_wrangler_in_package_json(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"wrangler": "^3.0.0"}})
    )
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_false_when_no_signal(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))
    assert CloudflareWorkersAdapter().detect(tmp_path) is False


def test_detect_false_on_missing_files(tmp_path):
    assert CloudflareWorkersAdapter().detect(tmp_path) is False


def test_inject_tracking_inserts_snippets(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.already_present is False
    assert change_set.changed_files == ("index.html",)

    updated = (tmp_path / "index.html").read_text()
    assert updated.count("GTM-ABC1234") == 2  # head 스니펫 + noscript 스니펫
    assert "googletagmanager.com/gtm.js" in updated
    assert "googletagmanager.com/ns.html" in updated
    # head 스니펫이 <head> 태그 바로 뒤에, noscript 스니펫이 <body> 태그 바로 뒤에 위치해야 함
    assert updated.index("<head>") < updated.index("gtm.js") < updated.index("<body>")
    assert updated.index("<body>") < updated.index("ns.html")


def test_inject_tracking_is_idempotent(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    adapter = CloudflareWorkersAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_inject_tracking_prefers_root_index_html(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set.changed_files == ("index.html",)
    assert "GTM-ABC1234" not in (tmp_path / "public" / "index.html").read_text()


def test_inject_tracking_falls_back_to_public_index_html(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set.changed_files == ("public/index.html",)


def test_inject_tracking_returns_none_when_no_html_entry(tmp_path):
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_inject_tracking_returns_none_when_html_missing_head_or_body(tmp_path):
    (tmp_path / "index.html").write_text("<div>no head or body tags</div>")
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None
