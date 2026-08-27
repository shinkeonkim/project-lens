from __future__ import annotations

import json

from project_lens.adapters.vercel import VercelAdapter

SAMPLE_HTML = """<!doctype html>
<html>
<head><title>t</title></head>
<body><div id="app"></div></body>
</html>
"""


def test_detect_true_with_vercel_json(tmp_path):
    (tmp_path / "vercel.json").write_text("{}\n")
    assert VercelAdapter().detect(tmp_path) is True


def test_detect_true_with_vercel_dependency(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"devDependencies": {"vercel": "^32.0.0"}}))
    assert VercelAdapter().detect(tmp_path) is True


def test_detect_false_without_signal(tmp_path):
    assert VercelAdapter().detect(tmp_path) is False


def test_detect_true_for_nested_project(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "vercel.json").write_text("{}\n")
    assert VercelAdapter().detect(tmp_path) is True


def test_inject_tracking_inserts_snippet(tmp_path):
    (tmp_path / "vercel.json").write_text("{}\n")
    (tmp_path / "index.html").write_text(SAMPLE_HTML)

    change_set = VercelAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("index.html",)
    assert "GTM-ABC1234" in (tmp_path / "index.html").read_text()


def test_inject_tracking_returns_none_without_vercel_signal(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    assert VercelAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None
