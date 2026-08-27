from __future__ import annotations

from project_lens.adapters.github_pages import GitHubPagesAdapter

SAMPLE_HTML = """<!doctype html>
<html>
<head><title>t</title></head>
<body><div id="app"></div></body>
</html>
"""

DEPLOY_PAGES_WORKFLOW = """
name: Deploy
on: push
jobs:
  deploy:
    steps:
      - uses: actions/deploy-pages@v4
"""


def test_detect_true_with_cname(tmp_path):
    (tmp_path / "CNAME").write_text("example.com\n")
    assert GitHubPagesAdapter().detect(tmp_path) is True


def test_detect_true_with_docs_cname(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CNAME").write_text("example.com\n")
    assert GitHubPagesAdapter().detect(tmp_path) is True


def test_detect_true_with_deploy_pages_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text(DEPLOY_PAGES_WORKFLOW)
    assert GitHubPagesAdapter().detect(tmp_path) is True


def test_detect_true_with_peaceiris_action(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text("- uses: peaceiris/actions-gh-pages@v3\n")
    assert GitHubPagesAdapter().detect(tmp_path) is True


def test_detect_false_with_unrelated_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("- uses: actions/checkout@v4\n")
    assert GitHubPagesAdapter().detect(tmp_path) is False


def test_detect_false_without_any_signal(tmp_path):
    assert GitHubPagesAdapter().detect(tmp_path) is False


def test_inject_tracking_uses_repo_root_index_html(tmp_path):
    (tmp_path / "CNAME").write_text("example.com\n")
    (tmp_path / "index.html").write_text(SAMPLE_HTML)

    change_set = GitHubPagesAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("index.html",)


def test_inject_tracking_falls_back_to_docs_dir(tmp_path):
    (tmp_path / "CNAME").write_text("example.com\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text(SAMPLE_HTML)

    change_set = GitHubPagesAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("docs/index.html",)


def test_inject_tracking_returns_none_without_pages_signal(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    assert GitHubPagesAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_inject_tracking_returns_none_when_no_content_found(tmp_path):
    (tmp_path / "CNAME").write_text("example.com\n")
    assert GitHubPagesAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None
