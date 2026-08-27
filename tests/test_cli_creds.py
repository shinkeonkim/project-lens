from __future__ import annotations

from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.google.ga4 import Ga4Account
from project_lens.google.gtm import GtmAccount
from project_lens.settings import load_settings


def test_creds_check_reports_missing_by_default(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["creds", "check"])

    assert result.exit_code == 0
    assert "google oauth: missing" in result.output
    assert "(미설정)" in result.output


def test_creds_init_google_runs_oauth_flow(lens_home, monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "run_oauth_flow", lambda: called.setdefault("ran", True))

    runner = CliRunner()
    result = runner.invoke(cli.main, ["creds", "init", "--provider", "google"])

    assert result.exit_code == 0
    assert called.get("ran") is True
    assert "완료" in result.output


def test_creds_set_accounts_persists_settings(lens_home):
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["creds", "set-accounts", "--ga4-account-id", "111", "--gtm-account-id", "222"],
    )

    assert result.exit_code == 0
    settings = load_settings()
    assert settings.ga4_account_id == "111"
    assert settings.gtm_account_id == "222"


def test_creds_set_accounts_partial_update_keeps_other_field(lens_home):
    runner = CliRunner()
    runner.invoke(cli.main, ["creds", "set-accounts", "--ga4-account-id", "111"])
    runner.invoke(cli.main, ["creds", "set-accounts", "--gtm-account-id", "222"])

    settings = load_settings()
    assert settings.ga4_account_id == "111"
    assert settings.gtm_account_id == "222"


def test_creds_accounts_lists_ga4_and_gtm(lens_home, monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: object())

    fake_ga4_module = cli.ga4
    fake_gtm_module = cli.gtm
    monkeypatch.setattr(fake_ga4_module, "build_client", lambda credentials: "ga4-client")
    monkeypatch.setattr(
        fake_ga4_module,
        "list_accounts",
        lambda client: [Ga4Account(id="111", display_name="shinkeonkim")],
    )
    monkeypatch.setattr(fake_gtm_module, "build_client", lambda credentials: "gtm-service")
    monkeypatch.setattr(
        fake_gtm_module,
        "list_accounts",
        lambda service: [GtmAccount(id="222", name="kokoa-lab")],
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["creds", "accounts"])

    assert result.exit_code == 0
    assert "111  shinkeonkim" in result.output
    assert "222  kokoa-lab" in result.output
