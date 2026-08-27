from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from project_lens.errors import DeployError
from project_lens.github import repo_ops


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode=1, stdout="", stderr=stderr)


def test_create_branch_success(monkeypatch, tmp_path):
    monkeypatch.setattr(repo_ops.subprocess, "run", lambda *a, **k: _ok())
    repo_ops.create_branch(tmp_path, "feat/x")  # 예외 없이 통과해야 함


def test_create_branch_failure_raises_deploy_error(monkeypatch, tmp_path):
    monkeypatch.setattr(repo_ops.subprocess, "run", lambda *a, **k: _fail("already exists"))
    with pytest.raises(DeployError):
        repo_ops.create_branch(tmp_path, "feat/x")


def test_commit_all_returns_sha(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["git", "rev-parse"]:
            return _ok("abc123\n")
        return _ok()

    monkeypatch.setattr(repo_ops.subprocess, "run", fake_run)
    sha = repo_ops.commit_all(tmp_path, "chore: add tracking")

    assert sha == "abc123"
    assert ["git", "add", "-A"] in calls
    assert ["git", "commit", "-m", "chore: add tracking"] in calls


def test_commit_all_failure_raises_deploy_error(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        if args[:2] == ["git", "commit"]:
            return _fail("nothing to commit")
        return _ok()

    monkeypatch.setattr(repo_ops.subprocess, "run", fake_run)
    with pytest.raises(DeployError):
        repo_ops.commit_all(tmp_path, "chore: add tracking")


def test_push_branch_failure_raises_deploy_error(monkeypatch, tmp_path):
    monkeypatch.setattr(repo_ops.subprocess, "run", lambda *a, **k: _fail("no permission"))
    with pytest.raises(DeployError):
        repo_ops.push_branch(tmp_path, "feat/x")


def test_create_pull_request_returns_url(monkeypatch, tmp_path):
    monkeypatch.setattr(
        repo_ops.subprocess,
        "run",
        lambda *a, **k: _ok("https://github.com/kokoa-lab/dice-art/pull/12\n"),
    )
    url = repo_ops.create_pull_request(
        tmp_path, title="t", body="b", base="main"
    )
    assert url == "https://github.com/kokoa-lab/dice-art/pull/12"


def test_create_pull_request_failure_raises_deploy_error(monkeypatch, tmp_path):
    monkeypatch.setattr(repo_ops.subprocess, "run", lambda *a, **k: _fail("no commits between"))
    with pytest.raises(DeployError):
        repo_ops.create_pull_request(tmp_path, title="t", body="b", base="main")


def test_create_issue_returns_url(monkeypatch, tmp_path):
    monkeypatch.setattr(
        repo_ops.subprocess,
        "run",
        lambda *a, **k: _ok("https://github.com/kokoa-lab/dice-art/issues/3\n"),
    )
    url = repo_ops.create_issue(tmp_path, title="t", body="b")
    assert url == "https://github.com/kokoa-lab/dice-art/issues/3"
