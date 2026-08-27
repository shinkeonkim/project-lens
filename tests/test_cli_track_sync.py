from __future__ import annotations

from contextlib import contextmanager

import pytest
from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.adapters.base import ChangeSet
from project_lens.registry.db import connect

SLUG = "kokoa-lab-dice-art"


class FakeAdapter:
    name = "fake"

    def __init__(self, *, detects: bool = True, change_set: ChangeSet | None = ChangeSet(
        changed_files=("index.html",), summary="index.html에 GTM(GTM-TEST) 스니펫을 삽입했습니다."
    )):
        self._detects = detects
        self._change_set = change_set
        self.inject_calls = []

    def detect(self, repo_path) -> bool:
        return self._detects

    def inject_tracking(self, repo_path, gtm_id: str):
        self.inject_calls.append((repo_path, gtm_id))
        return self._change_set


@pytest.fixture()
def registered_project(lens_home, fake_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"],
    )
    assert result.exit_code == 0
    return SLUG


@pytest.fixture()
def fake_workspace(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    @contextmanager
    def _fake_cloned_workspace(slug, token, url, *, keep=False):
        yield workspace_root

    monkeypatch.setattr(cli, "cloned_workspace", _fake_cloned_workspace)
    return workspace_root


def _run_count():
    conn = connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM deploy_runs").fetchone()[0]
    finally:
        conn.close()


def test_dry_run_does_not_touch_git_or_db(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter()
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])
    calls = {"branch": 0, "pr": 0, "issue": 0}
    monkeypatch.setattr(cli, "create_branch", lambda *a, **k: calls.__setitem__("branch", calls["branch"] + 1))
    monkeypatch.setattr(cli, "create_pull_request", lambda *a, **k: calls.__setitem__("pr", calls["pr"] + 1) or "unused")
    monkeypatch.setattr(cli, "create_issue", lambda *a, **k: calls.__setitem__("issue", calls["issue"] + 1) or "unused")

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST"])

    assert result.exit_code == 0, result.output
    assert "[dry-run]" in result.output
    assert calls == {"branch": 0, "pr": 0, "issue": 0}
    assert _run_count() == 0
    assert adapter.inject_calls, "dry-run에서도 diff 계산을 위해 inject_tracking은 호출되어야 함"


def test_yes_creates_branch_commit_push_pr(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter()
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])

    recorded = {}
    monkeypatch.setattr(cli, "create_branch", lambda repo_path, branch: recorded.__setitem__("branch", branch))
    monkeypatch.setattr(cli, "commit_all", lambda repo_path, message: "deadbeef")
    monkeypatch.setattr(cli, "push_branch", lambda repo_path, branch: recorded.__setitem__("pushed", branch))
    monkeypatch.setattr(
        cli,
        "create_pull_request",
        lambda repo_path, *, title, body, base: "https://github.com/kokoa-lab/dice-art/pull/1",
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST", "--yes"])

    assert result.exit_code == 0, result.output
    assert "https://github.com/kokoa-lab/dice-art/pull/1" in result.output
    assert recorded["branch"] == recorded["pushed"]
    assert _run_count() == 1

    conn = connect()
    try:
        row = conn.execute("SELECT status, pr_url, commit_sha FROM deploy_runs").fetchone()
        project_row = conn.execute("SELECT status FROM projects WHERE slug = ?", (SLUG,)).fetchone()
    finally:
        conn.close()

    assert row["status"] == "success"
    assert row["commit_sha"] == "deadbeef"
    assert row["pr_url"] == "https://github.com/kokoa-lab/dice-art/pull/1"
    assert project_row["status"] == "active"


def test_already_present_is_noop(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter(
        change_set=ChangeSet(changed_files=(), summary="이미 삽입되어 있습니다.", already_present=True)
    )
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])
    monkeypatch.setattr(cli, "create_branch", lambda *a, **k: pytest.fail("호출되면 안 됨"))

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST", "--yes"])

    assert result.exit_code == 0, result.output
    assert "이미 삽입되어 있습니다" in result.output

    conn = connect()
    try:
        row = conn.execute("SELECT status FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert row["status"] == "success"


def test_no_injection_point_dry_run_skips_issue(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter(change_set=None)
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])
    monkeypatch.setattr(cli, "create_issue", lambda *a, **k: pytest.fail("dry-run에서 호출되면 안 됨"))

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST"])

    assert result.exit_code == 0, result.output
    assert "찾지 못했습니다" in result.output
    assert _run_count() == 0


def test_no_injection_point_yes_creates_issue_and_flags_project(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter(change_set=None)
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])
    monkeypatch.setattr(
        cli, "create_issue", lambda repo_path, *, title, body: "https://github.com/kokoa-lab/dice-art/issues/9"
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST", "--yes"])

    assert result.exit_code == 0, result.output
    assert "issues/9" in result.output

    conn = connect()
    try:
        run_row = conn.execute("SELECT status FROM deploy_runs").fetchone()
        project_row = conn.execute("SELECT status FROM projects WHERE slug = ?", (SLUG,)).fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "partial"
    assert project_row["status"] == "needs_attention"


def test_adapter_not_detected_marks_run_failed(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter(detects=False)
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--gtm-id", "GTM-TEST", "--yes"])

    assert result.exit_code != 0

    conn = connect()
    try:
        run_row = conn.execute("SELECT status, error_code FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "failed"
    assert run_row["error_code"] == "AdapterDetectionError"


def test_unregistered_project_errors_without_touching_db(lens_home, fake_workspace):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", "no-such-slug", "--gtm-id", "GTM-TEST", "--yes"])

    assert result.exit_code != 0
    assert "등록되지 않은 프로젝트" in result.output


def test_auto_provision_dry_run_does_not_call_google_or_clone(registered_project, monkeypatch):
    monkeypatch.setattr(
        cli, "_provision_tracking", lambda conn, proj: pytest.fail("dry-run에서 호출되면 안 됨")
    )
    monkeypatch.setattr(
        cli, "cloned_workspace", lambda *a, **k: pytest.fail("dry-run auto 모드에서는 clone하면 안 됨")
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG])

    assert result.exit_code == 0, result.output
    assert "[dry-run]" in result.output
    assert "자동 생성" in result.output
    assert _run_count() == 0


def test_auto_provision_yes_calls_provisioning_then_injects(registered_project, fake_workspace, monkeypatch):
    adapter = FakeAdapter()
    monkeypatch.setattr(cli, "_ADAPTERS", [adapter])

    provision_calls = []

    def fake_provision(conn, proj):
        provision_calls.append(proj.slug)
        return "GTM-AUTO123"

    monkeypatch.setattr(cli, "_provision_tracking", fake_provision)
    monkeypatch.setattr(cli, "create_branch", lambda repo_path, branch: None)
    monkeypatch.setattr(cli, "commit_all", lambda repo_path, message: "deadbeef")
    monkeypatch.setattr(cli, "push_branch", lambda repo_path, branch: None)
    monkeypatch.setattr(
        cli,
        "create_pull_request",
        lambda repo_path, *, title, body, base: "https://github.com/kokoa-lab/dice-art/pull/2",
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--yes"])

    assert result.exit_code == 0, result.output
    assert provision_calls == [SLUG]
    assert adapter.inject_calls[0][1] == "GTM-AUTO123"
    assert "https://github.com/kokoa-lab/dice-art/pull/2" in result.output


def test_auto_provision_failure_marks_run_failed(registered_project, fake_workspace, monkeypatch):
    from project_lens.errors import ValidationError

    def fake_provision(conn, proj):
        raise ValidationError("GA4/GTM 기본 계정이 설정되지 않았습니다.")

    monkeypatch.setattr(cli, "_provision_tracking", fake_provision)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["track", "sync", SLUG, "--yes"])

    assert result.exit_code != 0

    conn = connect()
    try:
        run_row = conn.execute("SELECT status, error_code FROM deploy_runs").fetchone()
    finally:
        conn.close()
    assert run_row["status"] == "failed"
    assert run_row["error_code"] == "ValidationError"
