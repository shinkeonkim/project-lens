"""`lens dashboard --serve`용 로컬 전용 HTTP 서버.

project-lens는 클라우드에 아무것도 안 올린다는 원칙(docs/SECURITY.md)을 여기서도
지킨다 — 127.0.0.1에만 바인딩하고, 서드파티 웹 프레임워크 없이 stdlib
`http.server`만 쓴다. 목적은 하나: 대시보드 페이지 안의 "새로고침" 버튼이 터미널로
돌아가지 않고도 최신 데이터를 다시 불러오게 하는 것.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable


def run_dashboard_server(
    *, dashboard_path: Path, port: int, rebuild: Callable[[], str]
) -> None:
    """127.0.0.1:port에서 대시보드를 서빙한다. Ctrl+C로 멈출 때까지 블록한다.

    GET /            현재 dashboard.html 반환
    POST /refresh    rebuild()를 호출해 파일을 다시 쓰고 새 HTML을 반환
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            pass  # 매 요청마다 stderr에 access log를 찍지 않는다 — 터미널을 조용히 유지

        def _send_html(self, body: str, status: int = 200) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            # 로컬호스트 전용이라 민감정보 노출 우려는 없다 — file://로 열어도(다른
            # origin 취급) 새로고침 버튼이 동작하게 허용한다.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send_html(dashboard_path.read_text(encoding="utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/refresh":
                try:
                    html_content = rebuild()
                    self._send_html(html_content)
                except Exception as exc:  # noqa: BLE001
                    self._send_html(f"새로고침 실패: {exc}", status=500)
            else:
                self.send_response(404)
                self.end_headers()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
