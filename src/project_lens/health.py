"""등록된 프로젝트의 실제 사이트가 살아있는지 확인한다.

대시보드에서 "방문자 0"이 "트래픽이 없다"는 뜻인지 "사이트가 죽었다"는 뜻인지
구분이 안 되는 문제가 있었다 — 간단한 HTTP 상태 체크로 그 둘을 나눈다.
외부 라이브러리 없이 stdlib `urllib`만 쓴다(project-lens 전반의 방침, dashboard_server.py 참고).
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

_TIMEOUT_SECONDS = 6.0
_USER_AGENT = "project-lens-healthcheck/1.0"


def _to_ascii_url(url: str) -> str:
    """호스트명이 유니코드(예: cache-fridge.코드.kr)면 IDNA(퓨니코드)로 바꾼다.

    urllib은 브라우저와 달리 유니코드 호스트를 자동 변환하지 않는다 — 그대로
    요청하면 HTTP 헤더를 latin-1로 인코딩하는 과정에서 UnicodeEncodeError가 나서
    실제로는 멀쩡한 사이트가 전부 "응답 없음"으로 잘못 표시된다.
    """

    parts = urllib.parse.urlsplit(url)
    try:
        ascii_host = parts.hostname.encode("idna").decode("ascii") if parts.hostname else parts.hostname
    except UnicodeError:
        return url  # 변환 자체가 안 되면 원래 URL로 시도해서 자연스럽게 실패시킨다

    if ascii_host == parts.hostname:
        return url

    netloc = ascii_host
    if parts.port:
        netloc = f"{ascii_host}:{parts.port}"
    if parts.username:
        credentials = parts.username if not parts.password else f"{parts.username}:{parts.password}"
        netloc = f"{credentials}@{netloc}"
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@dataclass(frozen=True)
class SiteHealth:
    status: str  # "up" | "down" | "error" | "unknown"
    http_status: int | None = None
    detail: str | None = None


def check_site_health(url: str | None) -> SiteHealth:
    if not url:
        return SiteHealth(status="unknown")

    request = urllib.request.Request(_to_ascii_url(url), headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
            code = resp.status
            return SiteHealth(status="up" if code < 400 else "down", http_status=code)
    except urllib.error.HTTPError as exc:
        # 4xx/5xx도 "서버가 응답은 한다"는 뜻이라 down으로, 아예 응답이 없는 것과 구분한다.
        return SiteHealth(status="down", http_status=exc.code, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — DNS 실패, 타임아웃, TLS 에러 등 무엇이든 "down"
        return SiteHealth(status="down", detail=str(exc))
