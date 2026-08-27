"""docs/ARCHITECTURE.md에서 정의한 에러 타입 계층.

CLI는 이 예외들을 잡아 사람이 읽을 수 있는 요약 + 다음 행동을 출력한다.
각 타입은 향후 docs/TROUBLESHOOTING.md의 문제 해결 가이드와 매핑된다.
"""

from __future__ import annotations


class LensError(Exception):
    """모든 project-lens 예외의 기반 클래스."""


class ValidationError(LensError):
    """사용자 입력이 잘못된 경우 (예: URL 형식 오류)."""


class AuthError(LensError):
    """GitHub/Google 등 외부 서비스 인증이 되어 있지 않은 경우."""


class RepoAccessError(LensError):
    """레포가 존재하지 않거나 접근 권한이 없는 경우."""


class AdapterDetectionError(LensError):
    """배포 방식을 어떤 어댑터도 감지하지 못한 경우."""


class GoogleAPIError(LensError):
    """GA4/GTM/Ads API 호출 실패."""


class DeployError(LensError):
    """배포(PR 생성/직접 배포) 단계 실패."""


def short(exc: Exception) -> str:
    """Google API 예외의 첫 줄만 취한다.

    `GoogleAPICallError`/`GoogleAdsException`의 `str()`은 gRPC 메타데이터를 여러 줄에
    걸쳐 그대로 덤프해서, 리포트 여러 건을 한 화면에 모아 보여줄 때(`lens track
    report-all`) 한 건의 에러가 화면을 다 채워버린다. 원인 파악에 필요한 핵심 메시지는
    첫 줄에 있다.
    """
    return str(exc).split("\n", 1)[0]
