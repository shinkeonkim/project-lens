# 로드맵

각 Phase는 독립적으로 동작·검증 가능한 단위로 나눕니다. 이후 Phase가 늦어져도 이전 Phase의
가치(등록/이력 관리, PR 생성 등)는 그 자체로 사용 가능해야 합니다.

## Phase 0 — 스캐폴딩

- 레포 구조(`src/project_lens/...`), `pyproject.toml`, 콘솔 스크립트(`lens`) 등록
- SQLite 스키마 v1 + 마이그레이션 러너 (`docs/DATA_MODEL.md`)
- `gh auth status` 체크 유틸
- `lens project add <url> --metadata-only` — Google API/어댑터 없이 레지스트리 등록만
- `lens project list` / `lens project show <slug>`
- 산출물: REQUEST.md의 13개 레포를 실제로 등록해 레지스트리가 채워진 상태

## Phase 1 — Cloudflare Workers 어댑터 (트래킹 ID는 수동 입력)

- Workspace Manager (clone → 임시 디렉터리 → 정리)
- `CloudflareWorkersAdapter.detect()` / `inject_tracking()` (스니펫은 사용자가 미리 알고
  있는 기존 GTM ID를 `--gtm-id` 인자로 받아 삽입 — 아직 GTM API 연동 전)
- PR 생성 플로우 (`gh pr create`)
- 삽입 지점 자동 특정 실패 시 이슈 생성 폴백
- 검증: kokoa-lab 레포 1~2개에 대해 실제 PR이 정상 생성되는지 확인

## Phase 2 — GA4 + GTM API 연동

- [x] `google/auth.py` (OAuth 데스크톱 플로우 + keyring 저장), `lens creds init --provider google`
- [x] `ga4.py`: 계정 목록 조회, 속성/웹 스트림 조회-또는-생성 (idempotent)
- [x] `gtm.py`: 계정 목록 조회, 컨테이너/워크스페이스 조회-또는-생성, GA4 Configuration 태그 +
      "All Pages" pageview 트리거 생성, 워크스페이스 게시(publish)
- [x] `tracking_configs` 테이블 (migration 0003) — 프로젝트별 GA4/GTM ID 영속화
- [x] `projects.site_url` 컬럼 (migration 0004) + `lens project set-site-url` — GA4 웹
      스트림 생성에 필요한 실제 배포 URL 기록
- [x] `lens creds accounts` / `lens creds set-accounts` — GA4/GTM 기본 계정 ID 선택·저장
- [x] `lens track sync`의 `--gtm-id`를 선택 사항으로 전환: 생략하면 위 API로 자동
      생성/조회, dry-run(기본값)은 Google API를 전혀 호출하지 않고 계획만 출력
- [ ] **범위 축소**: 클릭/폼 제출/스크롤 이벤트 태그는 이번 Phase에 포함하지 않음 — GA4
      Configuration 태그(페이지뷰/세션 추적)까지만 자동화. 후속 작업으로 남겨둠
      (`gtm.py`에 `ensure_click_tag`/`ensure_form_tag`/`ensure_scroll_tag` 형태로 추가 예정)
- [x] **파일럿 완료**: `shinkeonkim/my-portfolio`에 실제 GA4 속성(`G-5WG1FMWKEN`) + GTM
      컨테이너(`GTM-NP2ZCHQF`) 생성·게시, `index.html`에 스니펫 삽입, 실제 PR
      ([#1](https://github.com/shinkeonkim/my-portfolio/pull/1)) 생성까지 end-to-end 확인.
      `tracking_configs`에 결과가 정상적으로 기록됨
- [x] 파일럿 과정에서 fake 테스트로는 못 잡은 실제 API 계약 차이 2건 발견 후 수정:
      GA4 Admin API `list_properties()`는 `filter=` 키워드 인자가 아니라
      `request={"filter": ...}` 형태로 호출해야 함, GTM 컨테이너 버전 생성
      (`create_version`)에는 `tagmanager.edit.containers`와 별도로
      `tagmanager.edit.containerversions` OAuth 스코프가 필요함 (`google/auth.py`
      `SCOPES`에 반영, 재인증 필요)

## Phase 3 — Google Ads 연동

- [x] `lens creds init --provider google-ads --developer-token ... [--login-customer-id ...]`
      — Developer Token은 keyring, login_customer_id는 settings.json에 저장
- [x] `google/auth.py` `SCOPES`에 `adwords` 스코프 추가 (기존 인증이 있었다면 재인증 필요)
- [x] `ga4.py`: `ensure_google_ads_link` — GA4 속성 ↔ Ads customer_id 연결 find-or-create
      (GA4 Admin API만으로 동작, Developer Token 불필요)
- [x] `ads.py`: `find_or_create_conversion_action` — 웹페이지 전환 액션 find-or-create.
      설치된 `google-ads`(v25) 패키지에서 실제 타입을 직접 import해 구현·테스트함
      (`client.get_type()`/`.enums`는 유효한 credentials 없이는 검증할 방법이 없어 사용 안 함)
- [x] `lens track link-ads <slug> --customer-id <ID> [--yes]` — dry-run 기본, GA4-Ads 연결은
      항상 시도하고 Developer Token이 있을 때만 전환 액션도 생성. `tracking_configs`의
      `ads_customer_id`/`ads_conversion_action_ids`에 결과 저장
- [ ] **라이브 검증 미완료**: 사용자가 아직 Google Ads 계정/Developer Token이 없어
      (신청 진행 중, 승인까지 수일 소요 예상) `ensure_google_ads_link`/
      `find_or_create_conversion_action` 둘 다 fake 기반 단위 테스트로만 검증됨.
      Phase 2의 GA4 API 실사용 검증에서 문서만으로 예측한 호출 방식이 실제와 2군데
      달랐던 전례가 있으므로, Ads 계정이 생기는 대로 반드시 `lens track link-ads`
      실사용 검증을 거쳐야 함
- [ ] `/lens-report`: GA4 방문자/세션/이탈률 + Ads CTR/전환율/광고비 통합 리포트
      (착수 전 — 의미 있는 리포트를 보려면 실제 트래픽/전환 데이터가 어느 정도 쌓여야 함)

## Phase 4 — oh-my-homelab 어댑터

- [x] `shinkeonkim/oh-my-homelab`, `shinkeonkim/codekr` 조사 완료 — 정적 사이트가 아니라
      Next.js(App Router) 웹 + Go/Kotlin 백엔드로 구성된 코딩 테스트 플랫폼, K8s +
      ArgoCD GitOps로 배포. 상세 내용은 [`ADAPTERS.md`](ADAPTERS.md#ohmyhomelabadapter) 참고
- [x] `OhMyHomelabAdapter` 구현 — codekr의 실제 파일 구조에 맞춘 앵커 기반 패치
      (Next.js 컴포넌트 추가, layout.tsx/Dockerfile/.env.example/CI 워크플로 배선) +
      `configure_remote()`로 GitHub Actions 저장소 변수 설정(`--yes`일 때만)
- [x] **범위 판단**: `oh-my-homelab`(private, ArgoCD `selfHeal: true`로 운영 클러스터에
      자동 반영)은 전혀 건드리지 않기로 함 — GTM ID가 Next.js 빌드 시점에 굳는 값이라
      codekr 자신의 CI 저장소 변수로 충분했고, 위험을 public 레포(PR 리뷰 가능) 안에
      가둘 수 있었음
- [x] **검증 완료**: 실제로 clone해 `bun install && bun run lint && bun run typecheck &&
      bun run build && bun test`를 로컬에서 직접 돌려 확인(lint 0 errors, 47개 라우트
      빌드 성공, 기존 웹 테스트 184개 통과) 후 `lens track sync shinkeonkim-codekr --yes`
      실행 → GA4 속성(`G-NZE9ZMZRZD`)/GTM 컨테이너(`GTM-TP9LLDRJ`) 실제 생성, 저장소 변수
      설정, PR [#667](https://github.com/shinkeonkim/codekr/pull/667) 생성. 실제 GitHub
      CI(`web` 검사: 테스트·커버리지·린트·타입체크·빌드)도 전부 통과 확인

## Phase 5 — 운영 품질

- [x] 전체 14개 등록 레포에 `lens track sync <slug> --gtm-id ...`(dry-run)를 일괄 실행해
      어댑터 커버리지 확인 → **14개 전부 유효한 삽입 계획 확인, 100% 커버리지**
- [x] 커버리지 점검 중 발견한 실제 문제 2건을 고침:
      - `kokoa-study-room/compiler-study-site`는 `deployment_type=cloudflare_workers`가
        맞았는데(`wrangler.jsonc` 존재) 실제 사이트가 `site/` 서브디렉터리 안에 있고
        `CloudflareWorkersAdapter.detect()`가 레포 루트만 봐서 놓치고 있었음 → 서브디렉터리
        한 단계까지 찾도록 수정
      - 그 사이트와 `terraform-associate-004-study-notes`는 각각 Docusaurus·Astro
        Starlight로 만들어져 소스에 정적 `index.html`이 없음 → 각 프레임워크의 공식 GTM
        설정 방식(Docusaurus `googleTagManager` 프리셋 옵션, Starlight `head` 옵션)으로
        패치하는 전략을 추가하고 실제 레포로 clone → 패치 → `bun run build`까지 돌려
        빌드된 HTML에 스니펫이 실제로 들어가는 것을 확인
- [x] `docs/TROUBLESHOOTING.md` 작성 — 기존 에러 타입 6개(`errors.py`)별 원인/해결 절차,
      이 프로젝트를 만들면서 실제로 겪은 사례(OAuth 스코프 드리프트, GA4/GTM API 계약
      불일치) 포함
- [x] `lens logs show <run_id>` 구현 (기존엔 설계만 있었음) — `deploy_runs` 1건 상세 +
      에러 타입별 힌트. `lens project show`도 프로젝트 메타데이터에 이어 가장 최근 실행
      (PR/이슈 링크 또는 실패 원인)을 함께 보여주도록 확장 — `needs_attention` 상태만
      보고 "왜"를 알 수 없던 문제 해결
- [x] 빠졌던 `/lens-logs` 슬래시 커맨드 추가, `/lens-status` 설명 최신화
- [x] README/SECURITY 문서 최종 점검 — README에 현재 상태(실제 PR 링크)·빠른 시작 섹션
      추가, 전체 문서에서 미구현 커맨드를 가리키는 stale 링크 없는지 확인

## Phase 6 — 향후 확장 (사용자 요청으로 전부 구현, 실사용 필요는 아직 없었음)

원래 "설계만, 착수 안 함"으로 뒀던 Phase였으나, 사용자가 명시적으로 지금 다 구현해
두길 원해 진행했다. 아래 항목 전부 실제 필요(현재 등록된 프로젝트에 Vercel/GitHub
Pages 배포가 없고, 정기 리포트/다중 계정 요구도 없었음)보다 먼저 만든 것이므로,
실사용 검증은 다음에 그 필요가 생겼을 때 하게 된다 — 코드는 fake/로컬 테스트로만
검증됨(GA4/GTM/Ads 클라이언트 코드가 그래왔듯, 실제 사용 시 API 계약이 예상과 다를
수 있다는 전례가 이미 여러 번 있었다).

- [x] **VercelAdapter/GitHubPagesAdapter 추가** — Cloudflare 어댑터의 정적 사이트 삽입
      로직(HTML/Docusaurus/Starlight)을 `adapters/_static_site.py` 공유 모듈로 뽑아내
      세 어댑터가 재사용. `deployment_type` CHECK 제약에 `vercel`/`github_pages` 추가
      (migration 0005 — SQLite CHECK 제약 변경은 테이블 재생성이 필요했고, 외래키
      때문에 `PRAGMA foreign_keys=OFF`로 감싸야 했음. 실제 등록된 14개 프로젝트 DB의
      **사본**으로 먼저 검증한 뒤 라이브 DB에 적용)
- [x] **다중 GA4/Ads 계정 프로필 지원** — `settings.py`가 이름 붙은 `AccountProfile`
      여러 개 + `org_profile_map`(GitHub org → 프로필)을 저장하도록 확장.
      `lens creds set-accounts --profile <이름>`, `lens creds map-org <org> <profile>`.
      기존 평평한 settings.json은 자동으로 `default` 프로필로 승격(하위 호환 확인됨)
- [x] **`lens track report`/`report-all`** — GA4 Data API(Admin API와 별개 서비스, 별도
      OAuth 스코프 `analytics.readonly` + GCP 프로젝트에서 API 활성화 둘 다 필요했음 —
      실사용 검증 중 발견) 기반 방문자/세션/이탈률 리포트, 연결됐으면 Ads 지표도.
      `report-all`은 등록된 모든 프로젝트를 순회하며 개별 실패에도 계속 진행하고
      `~/.project-lens/reports/`에 저장
- [x] **정기 리포트 스케줄링** — 클라우드 `schedule` 스킬은 project-lens의 "비밀은
      로컬에만" 원칙과 충돌해(클라우드 샌드박스가 로컬 키체인/SQLite에 접근 불가)
      대신 로컬 launchd LaunchAgent를 씀(`docs/SCHEDULED_REPORTS.md`,
      `scripts/launchd/`). 매주 월요일 9시, `lens track report-all` 실행. **실제로
      등록해서 `launchctl kickstart`로 완전한 성공까지 검증 완료** — 로그인 세션
      없이도 키체인 접근이 되는지 확인했고, 재시도 후 14개 프로젝트 전부의 실제
      GA4 리포트가 로그·`~/.project-lens/reports/`에 정상적으로 남는 것까지 확인함

## Phase 간 의존성

```
Phase 0 ─▶ Phase 1 ─▶ Phase 2 ─▶ Phase 3
                 └────────────▶ Phase 4 (Phase 1의 어댑터 계약만 있으면 착수 가능)
Phase 2, 3, 4 완료 후 ─▶ Phase 5 ─▶ Phase 6
```

Phase 4(oh-my-homelab)는 Phase 2/3(Google API)와 독립적이므로, 조사 스파이크는 Phase 1
완료 직후 아무 때나 병행 착수 가능합니다.
