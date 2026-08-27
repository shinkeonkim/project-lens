from __future__ import annotations

import keyring.errors
import pytest

import project_lens.cli as cli
import project_lens.google.auth as google_auth
from project_lens.github.client import RepoInfo


class _FakeKeyringStore:
    """keyring 대체용 인메모리 저장소. 실제 OS 키체인을 절대 건드리지 않기 위함."""

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, value):
        self.values[(service, username)] = value

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        try:
            del self.values[(service, username)]
        except KeyError as exc:
            raise keyring.errors.PasswordDeleteError() from exc


@pytest.fixture()
def fake_keyring(monkeypatch):
    """OS 키체인을 인메모리 대역으로 교체한다 (테스트가 실제 키체인 상태에 의존하지 않도록)."""

    store = _FakeKeyringStore()
    monkeypatch.setattr(google_auth.keyring, "set_password", store.set_password)
    monkeypatch.setattr(google_auth.keyring, "get_password", store.get_password)
    monkeypatch.setattr(google_auth.keyring, "delete_password", store.delete_password)
    return store


@pytest.fixture()
def lens_home(tmp_path, monkeypatch, fake_keyring):
    """PROJECT_LENS_HOME과 keyring을 임시/인메모리로 격리해 실제 사용자 상태를 건드리지 않는다."""

    monkeypatch.setenv("PROJECT_LENS_HOME", str(tmp_path / "project-lens-home"))
    return tmp_path


@pytest.fixture()
def fake_repo(monkeypatch):
    """gh CLI 호출 없이 kokoa-lab/dice-art 레포 조회 결과를 흉내낸다."""

    monkeypatch.setattr(cli, "ensure_authenticated", lambda: None)
    monkeypatch.setattr(
        cli,
        "view_repo",
        lambda url: RepoInfo(
            org="kokoa-lab",
            repo="dice-art",
            url=url,
            visibility="public",
            default_branch="main",
        ),
    )
