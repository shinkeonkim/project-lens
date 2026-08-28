from __future__ import annotations

import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from project_lens.dashboard_server import run_dashboard_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def running_server(tmp_path):
    dashboard_path = tmp_path / "dashboard.html"
    dashboard_path.write_text("<html>initial</html>", encoding="utf-8")
    port = _free_port()
    calls = []

    def rebuild() -> str:
        calls.append(1)
        new_html = f"<html>refreshed {len(calls)}</html>"
        dashboard_path.write_text(new_html, encoding="utf-8")
        return new_html

    thread = threading.Thread(
        target=run_dashboard_server,
        kwargs={"dashboard_path": dashboard_path, "port": port, "rebuild": rebuild},
        daemon=True,
    )
    thread.start()

    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.2)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)

    yield port, calls


def test_get_serves_current_dashboard_file(running_server):
    port, _ = running_server
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        assert resp.status == 200
        assert resp.read().decode() == "<html>initial</html>"


def test_post_refresh_rebuilds_and_returns_new_html(running_server):
    port, calls = running_server
    req = urllib.request.Request(f"http://127.0.0.1:{port}/refresh", method="POST")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.read().decode() == "<html>refreshed 1</html>"
    assert calls == [1]

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        assert resp.read().decode() == "<html>refreshed 1</html>"


def test_refresh_failure_returns_500_without_crashing_server(tmp_path):
    dashboard_path = tmp_path / "dashboard.html"
    dashboard_path.write_text("<html>initial</html>", encoding="utf-8")
    port = _free_port()
    attempts = []

    def flaky_rebuild() -> str:
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("GA4 API 호출 실패")
        return "<html>recovered</html>"

    thread = threading.Thread(
        target=run_dashboard_server,
        kwargs={"dashboard_path": dashboard_path, "port": port, "rebuild": flaky_rebuild},
        daemon=True,
    )
    thread.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.2)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)

    req = urllib.request.Request(f"http://127.0.0.1:{port}/refresh", method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 500

    # 서버가 죽지 않았는지 — 다음 refresh는 성공해야 한다.
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.read().decode() == "<html>recovered</html>"


def test_unknown_path_returns_404(running_server):
    port, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
    assert exc_info.value.code == 404
