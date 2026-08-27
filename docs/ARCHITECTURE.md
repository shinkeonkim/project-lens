# 아키텍처

## 레이어 구성

```
┌─────────────────────────────────────────────────────────┐
│ Claude Code Command Layer  (.claude/commands/lens-*.md)  │
│  자연어 요청 → lens CLI 호출 → 결과 요약                    │
└───────────────────────────┬───────────────────────────────┘
                             │ subprocess
┌───────────────────────────▼───────────────────────────────┐
│ Python CLI  (lens)                                         │
│  project / track / deploy / creds / logs 서브커맨드          │
└───────────────────────────┬───────────────────────────────┘
                             │
     ┌───────────┬──────────┼──────────┬───────────────┐
     ▼           ▼          ▼          ▼               ▼
 Registry    GitHub     Workspace   Deployment      Google
 Service     Service    Manager     Adapters        Marketing
 (SQLite)    (gh CLI)   (clone/     (Cloudflare     Service
                         cleanup)    Workers,        (GA4/GTM/Ads
                                     oh-my-homelab)   API 클라이언트)
```

Claude Code 커맨드는 "얇은 레이어"로 유지합니다. 실제 판단/부수효과는 전부 Python CLI 쪽 테스트
가능한 코드에 있고, 커맨드 마크다운은 사용자의 자연어 요청을 CLI 인자로 정리해 실행하고, 그 결과를
사람이 읽기 좋은 형태로 요약하는 역할만 합니다.

## 핵심 컴포넌트

### 1. Registry Service (SQLite)

프로젝트/트래킹 설정/실행 이력을 저장하는 단일 진실 소스. 스키마는
[`DATA_MODEL.md`](DATA_MODEL.md) 참고. DB 파일(`~/.project-lens/registry.sqlite3`)은 저장소
바깥, 사용자 홈 디렉터리에 둡니다 — project-lens 레포 자체에는 코드/문서만 존재하고, 실행 상태는
로컬 머신에만 남습니다.

### 2. GitHub Service

`gh` CLI를 subprocess로 감쌉니다. 이미 로그인된 `gh auth` 세션을 재사용하므로 이 프로젝트가
별도 토큰을 발급/보관하지 않습니다.

- `gh repo view <url> --json ...` — 존재 여부, 가시성(public/private), 접근 권한, 기본 브랜치 확인
- `gh repo clone <url> <path>` — 임시 워크스페이스로 clone (private 레포도 gh 인증으로 동작)
- 접근 실패 시(권한 없음/미인증) 에러를 그대로 삼키지 않고 `RepoAccessError`로 변환해
  `gh auth login` 또는 조직 접근 요청 안내를 사용자에게 보여줍니다.

### 3. Workspace Manager

"작업 시에만 clone, 끝나면 삭제" 원칙을 강제하는 컴포넌트.

- 실행마다 `~/.project-lens/workspace/<slug>-<run_id>/` 임시 디렉터리 생성
- 성공/실패와 무관하게 `try/finally`로 정리 — 실패해도 코드가 로컬에 남지 않음
- 디버깅 목적의 `--keep-workspace` 플래그로만 예외적으로 보존 (기본값 off)
- 동시에 같은 프로젝트에 대해 두 실행이 겹치지 않도록 프로젝트 단위 파일 락 사용

### 4. Deployment Adapters

배포 방식이 프로젝트마다 다르므로 어댑터 패턴으로 분리합니다. 공통 인터페이스:

```python
class DeploymentAdapter(Protocol):
    def detect(self, repo_path: Path) -> bool: ...
    def inject_tracking(self, repo_path: Path, config: TrackingConfig) -> ChangeSet: ...
    def deploy(self, repo_path: Path, change_set: ChangeSet, mode: Literal["pr", "direct"]) -> DeployResult: ...
```

- `detect()`가 `True`를 반환하는 첫 어댑터가 선택됩니다 (등록 순서 = 우선순위).
- 초기 구현 대상: `CloudflareWorkersAdapter`, `OhMyHomelabAdapter`. 상세 명세는
  [`ADAPTERS.md`](ADAPTERS.md).
- 새 배포 방식(Vercel, GitHub Pages 등) 추가 시 어댑터만 새로 작성하면 되고 core 로직은 불변.
- 기본 배포 모드는 **PR 생성**(`mode="pr"`). 직접 배포(`mode="direct"`)는 프로젝트별로
  `projects.deploy_mode` 설정을 통해 옵트인해야만 동작 — 검증 없는 자동 배포 사고를 방지.

### 5. Google Marketing Service

GA4 Admin API, Tag Manager API v2, Google Ads API를 감싸는 클라이언트 모듈.

- `ga4.py` — 속성(property)/데이터 스트림 조회 또는 생성, measurement ID 확보
- `gtm.py` — 계정/컨테이너/워크스페이스 조회 또는 생성, 기본 태그(GA4 Configuration Tag) +
  트리거(클릭/폼 제출/스크롤) 생성, 워크스페이스 게시(publish)
- `ads.py` — 전환 액션 생성/조회, GA4 ↔ Ads 연결 확인, 캠페인 성과 지표 조회(리포트용)
- 모든 API 호출은 idempotent하게 설계 — "없으면 생성, 있으면 조회"로 재실행 안전성 확보

### 6. Credential Manager

Google API 자격증명(OAuth refresh token, Ads developer token 등)을 OS 키체인(`keyring`
패키지) 또는 저장소 바깥의 `~/.project-lens/credentials/`에 보관합니다. 상세 설정 절차는
[`SECURITY.md`](SECURITY.md).

### 7. Logger / Audit

- 실행별 구조화 로그: `~/.project-lens/logs/<date>/<run_id>.jsonl`
- 실행 요약은 `deploy_runs` 테이블에도 저장되어 `/lens-status`, `/lens-logs`로 조회 가능
- 에러는 타입화된 예외 계층(`AuthError`, `RepoAccessError`, `AdapterDetectionError`,
  `GoogleAPIError`, `DeployError`)으로 구분되고, 각 타입은 문제 해결 가이드
  (`docs/TROUBLESHOOTING.md`, 로드맵 Phase 5에서 작성)와 매핑됩니다.

## 대표 워크플로우: 신규 프로젝트 등록 및 최초 세팅

`/lens-add-project https://github.com/kokoa-lab/dice-art` 호출 시:

1. URL 파싱 → org/repo/slug 도출
2. `gh repo view`로 접근 가능 여부·가시성 확인, 실패 시 안내 후 중단
3. `projects` 테이블에 upsert (status=`pending`)
4. Workspace Manager가 임시 디렉터리에 clone
5. Deployment Adapter 체인이 배포 방식 감지 (여기서는 Cloudflare Workers)
6. 기존 `tracking_configs`가 없으면 GA4 속성/스트림 + GTM 컨테이너/워크스페이스/기본 태그를
   API로 생성, 있으면 조회 후 값 검증
7. Adapter가 저장소에 GTM 스니펫/설정 삽입 (브랜치 생성 + 커밋)
8. 기본 모드는 PR 생성. 프로젝트가 `deploy_mode=direct`로 설정돼 있으면 배포까지 수행
9. `deploy_runs`, `tracking_configs.last_synced_at` 갱신
10. 임시 디렉터리 삭제
11. 결과 요약 (PR 링크 또는 배포 URL, GA4 measurement ID, GTM container ID, 남은 수동 작업
    — 예: "Google Ads 전환 액션 연결은 개발자 토큰 승인 후 `/lens-sync`로 재실행하세요")

재동기화(`/lens-sync`)는 3~10단계를 반복하되, 이미 존재하는 트래킹 설정은 재생성하지 않고
저장소에 스니펫이 여전히 존재하는지만 검증(drift 감지)합니다.
