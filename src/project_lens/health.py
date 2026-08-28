"""등록된 프로젝트의 실제 사이트가 살아있는지 확인한다.

대시보드에서 "방문자 0"이 "트래픽이 없다"는 뜻인지 "사이트가 죽었다"는 뜻인지
구분이 안 되는 문제가 있었다 — 간단한 HTTP 상태 체크로 그 둘을 나눈다.
외부 라이브러리 없이 stdlib `urllib`만 쓴다(project-lens 전반의 방침, dashboard_server.py 참고).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

_TIMEOUT_SECONDS = 6.0
_USER_AGENT = "project-lens-healthcheck/1.0"


@dataclass(frozen=True)
class SiteHealth:
    status: str  # "up" | "down" | "error" | "unknown"
    http_status: int | None = None
    detail: str | None = None


def check_site_health(url: str | None) -> SiteHealth:
    if not url:
        return SiteHealth(status="unknown")

    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
            code = resp.status
            return SiteHealth(status="up" if code < 400 else "down", http_status=code)
    except urllib.error.HTTPError as exc:
        # 4xx/5xx도 "서버가 응답은 한다"는 뜻이라 down으로, 아예 응답이 없는 것과 구분한다.
        return SiteHealth(status="down", http_status=exc.code, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — DNS 실패, 타임아웃, TLS 에러 등 무엇이든 "down"
        return SiteHealth(status="down", detail=str(exc))
