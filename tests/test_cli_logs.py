from __future__ import annotations

from click.testing import CliRunner

import project_lens.cli as cli
from project_lens.registry.db import connect
from project_lens.registry.repository import finish_run, get_project, start_run

SLUG = "kokoa-lab-dice-art"


def _register(runner):
    result = runner.invoke(
        cli.main,
        ["project", "add", "https://github.com/kokoa-lab/dice-art", "--metadata-only"],
    )
    assert result.exit_code == 0


def test_project_show_with_no_runs(lens_home, fake_repo):
    runner = CliRunner()
    _register(runner)

    result = runner.invoke(cli.main, ["project", "show", SLUG])

    assert result.exit_code == 0
    assert "최근 실행" in result.output
    assert "없음" in result.output


def test_project_show_with_failed_run_shows_hint(lens_home, fake_repo):
    runner = CliRunner()
    _register(runner)

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        run_id = start_run(conn, project_id=proj.id, run_type="sync")
        finish_run(
            conn,
            run_id,
            status="failed",
            error_code="GoogleAPIError",
            error_summary="insufficient scope",
        )
    finally:
        conn.close()

    result = runner.invoke(cli.main, ["project", "show", SLUG])

    assert result.exit_code == 0
    assert f"run_id: {run_id}" in result.output
    assert "GoogleAPIError" in result.output
    assert "TROUBLESHOOTING.md" in result.output


def test_project_show_with_successful_run_shows_pr(lens_home, fake_repo):
    runner = CliRunner()
    _register(runner)

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        run_id = start_run(conn, project_id=proj.id, run_type="sync")
        finish_run(
            conn,
            run_id,
            status="success",
            pr_url="https://github.com/kokoa-lab/dice-art/pull/1",
            summary="GTM 삽입 완료",
        )
    finally:
        conn.close()

    result = runner.invoke(cli.main, ["project", "show", SLUG])

    assert result.exit_code == 0
    assert "https://github.com/kokoa-lab/dice-art/pull/1" in result.output
    assert "GTM 삽입 완료" in result.output


def test_logs_show_unknown_run_id(lens_home):
    runner = CliRunner()
    result = runner.invoke(cli.main, ["logs", "show", "999"])
    assert result.exit_code != 0
    assert "존재하지 않는 run_id" in result.output


def test_logs_show_failed_run_includes_hint(lens_home, fake_repo):
    runner = CliRunner()
    _register(runner)

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        run_id = start_run(conn, project_id=proj.id, run_type="sync")
        finish_run(
            conn, run_id, status="failed", error_code="AuthError", error_summary="not logged in"
        )
    finally:
        conn.close()

    result = runner.invoke(cli.main, ["logs", "show", str(run_id)])

    assert result.exit_code == 0
    assert "AuthError" in result.output
    assert "힌트:" in result.output
    assert "creds check" in result.output


def test_logs_show_unknown_error_code_falls_back_gracefully(lens_home, fake_repo):
    runner = CliRunner()
    _register(runner)

    conn = connect()
    try:
        proj = get_project(conn, SLUG)
        run_id = start_run(conn, project_id=proj.id, run_type="sync")
        finish_run(conn, run_id, status="failed", error_code="SomethingNew", error_summary="?")
    finally:
        conn.close()

    result = runner.invoke(cli.main, ["logs", "show", str(run_id)])

    assert result.exit_code == 0
    assert "알 수 없는 에러 타입" in result.output
