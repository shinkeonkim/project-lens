from __future__ import annotations

from click.testing import CliRunner

import project_lens.cli as cli


def test_project_add_requires_metadata_only_flag(lens_home, fake_repo):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["project", "add", "https://github.com/kokoa-lab/dice-art"])
    assert result.exit_code != 0
    assert "--metadata-only" in result.output


def test_project_add_and_list(lens_home, fake_repo):
    runner = CliRunner()
    add_result = runner.invoke(
        cli.main,
        ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"],
    )
    assert add_result.exit_code == 0
    assert "kokoa-lab-dice-art" in add_result.output

    list_result = runner.invoke(cli.main, ["project", "list"])
    assert list_result.exit_code == 0
    assert "kokoa-lab-dice-art" in list_result.output


def test_project_show_unknown_slug(lens_home, fake_repo):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["project", "show", "no-such-project"])
    assert result.exit_code != 0
    assert "no-such-project" in result.output


def test_project_list_empty(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["project", "list"])
    assert result.exit_code == 0
    assert "등록된 프로젝트가 없습니다" in result.output
