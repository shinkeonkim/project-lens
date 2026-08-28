from __future__ import annotations

import base64
import json
import subprocess

import pytest

from project_lens.errors import AuthError, RepoAccessError, ValidationError
from project_lens.github.client import (
    ensure_authenticated,
    fetch_dependabot_alerts,
    fetch_license,
    fetch_readme,
    parse_github_url,
    view_repo,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/kokoa-lab/dice-art", ("kokoa-lab", "dice-art")),
        ("https://github.com/kokoa-lab/dice-art/", ("kokoa-lab", "dice-art")),
        ("https://github.com/kokoa-lab/dice-art.git", ("kokoa-lab", "dice-art")),
        ("git@github.com:kokoa-lab/dice-art.git", ("kokoa-lab", "dice-art")),
    ],
)
def test_parse_github_url_valid(url, expected):
    assert parse_github_url(url) == expected


@pytest.mark.parametrize("url", ["not-a-url", "https://gitlab.com/org/repo", ""])
def test_parse_github_url_invalid(url):
    with pytest.raises(ValidationError):
        parse_github_url(url)


def test_ensure_authenticated_raises_when_gh_not_logged_in(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="not logged in")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AuthError):
        ensure_authenticated()


def test_ensure_authenticated_passes_when_logged_in(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ensure_authenticated()  # 예외 없이 통과해야 함


def test_view_repo_success(monkeypatch):
    payload = {
        "nameWithOwner": "kokoa-lab/dice-art",
        "owner": {"login": "kokoa-lab"},
        "name": "dice-art",
        "url": "https://github.com/kokoa-lab/dice-art",
        "visibility": "PUBLIC",
        "isPrivate": False,
        "defaultBranchRef": {"name": "main"},
    }

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    info = view_repo("https://github.com/kokoa-lab/dice-art")

    assert info.org == "kokoa-lab"
    assert info.repo == "dice-art"
    assert info.visibility == "public"
    assert info.default_branch == "main"


def test_view_repo_not_accessible(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args, returncode=1, stdout="", stderr="GraphQL: Could not resolve to a Repository"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RepoAccessError):
        view_repo("https://github.com/kokoa-lab/does-not-exist")


def test_fetch_readme_decodes_base64_content(monkeypatch):
    encoded = base64.b64encode("# hello\n".encode("utf-8")).decode("ascii")

    def fake_run(args, **kwargs):
        assert args == ["gh", "api", "repos/shinkeonkim/qr-gen/readme", "--jq", ".content"]
        return subprocess.CompletedProcess(args, returncode=0, stdout=f"{encoded}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert fetch_readme("shinkeonkim", "qr-gen") == "# hello\n"


def test_fetch_readme_returns_none_when_missing(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="404")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert fetch_readme("shinkeonkim", "no-readme-repo") is None


def test_fetch_license_returns_name_when_present(monkeypatch):
    def fake_run(args, **kwargs):
        assert args == ["gh", "api", "repos/shinkeonkim/project-lens/license", "--jq", ".license.name"]
        return subprocess.CompletedProcess(args, returncode=0, stdout="MIT License\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert fetch_license("shinkeonkim", "project-lens") == "MIT License"


def test_fetch_license_returns_none_when_missing(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="404")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert fetch_license("kokoa-lab", "no-license-repo") is None


def test_fetch_dependabot_alerts_returns_open_alerts(monkeypatch):
    payload = json.dumps(
        [
            {"severity": "high", "package": "requests"},
            {"severity": "critical", "package": "lodash"},
        ]
    )

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = fetch_dependabot_alerts("kokoa-lab", "dice-art")
    assert result.status == "ok"
    assert len(result.alerts) == 2
    assert result.alerts[0]["severity"] == "high"


def test_fetch_dependabot_alerts_uses_query_string_not_dash_f(monkeypatch):
    """실제로 겪은 버그의 회귀 테스트: `gh api -f state=open ...`는 gh가 -f/-F가

    있으면 메서드를 자동으로 POST로 바꿔버려서(GET만 지원하는 이 엔드포인트가) 항상
    404가 났다. state=open은 반드시 URL 쿼리스트링으로 넘겨야 한다."""

    def fake_run(args, **kwargs):
        assert args == [
            "gh",
            "api",
            "repos/kokoa-lab/dice-art/dependabot/alerts?state=open",
            "--jq",
            "[.[] | {severity: .security_advisory.severity, package: .dependency.package.name}]",
        ]
        assert "-f" not in args
        return subprocess.CompletedProcess(args, returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    fetch_dependabot_alerts("kokoa-lab", "dice-art")


def test_fetch_dependabot_alerts_detects_disabled_repo(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            returncode=1,
            stdout="",
            stderr='{"message":"Dependabot alerts are disabled for this repository."}',
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = fetch_dependabot_alerts("shinkeonkim", "base64-code")
    assert result.status == "disabled"
    assert result.alerts == ()


def test_fetch_dependabot_alerts_returns_error_on_other_failure(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="rate limited")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = fetch_dependabot_alerts("shinkeonkim", "some-repo")
    assert result.status == "error"
