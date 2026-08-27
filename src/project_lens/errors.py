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
