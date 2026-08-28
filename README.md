# project-lens

여러 웹사이트 프로젝트의 Google Analytics(GA4) / Google Tag Manager(GTM) / Google Ads /
AdSense 설정을 한 곳에서 등록·자동화·감사하는 로컬 CLI입니다. 실제 상태는 로컬
SQLite 레지스트리 하나가 갖고 있고, 비밀값은 전부 OS 키체인에만 저장합니다 —
project-lens 자체는 어떤 클라우드에도 아무것도 올리지 않습니다.

Claude Code 안에서는 CLI 대신 `/lens-add-project`, `/lens-sync` 같은 슬래시 커맨드로
씁니다(`.claude/commands/`).

## 왜 필요한가

- 개인/스터디/랩에서 운영 중인 웹사이트가 여러 개이고, 배포 방식(Cloudflare
  Workers, Vercel, GitHub Pages, oh-my-homelab/K8s)도 제각각입니다.
- 사이트마다 GA4 속성·GTM 컨테이너·Ads 전환 액션·AdSense 연결을 손으로 만들면
  누락·불일치가 생기기 쉽습니다.
- 작업할 때만 레포를 clone하고 끝나면 삭제하여, 로컬에 여러 프로젝트 코드를
  쌓아두지 않아야 합니다.
- 어떤 프로젝트를 언제 어떻게 세팅했는지 기록이 남아야 재작업·비교·감사(audit)가
  가능합니다.

## 핵심 기능

**추적 설정 자동화**
- GA4 속성 + 웹 스트림, GTM 컨테이너 + Configuration 태그를 API로 find-or-create
- 배포 방식에 맞는 위치에 GTM 스니펫을 삽입하고 PR(또는 삽입 지점을 못 찾으면 이슈)
  자동 생성
- GA4 속성 ↔ Google Ads 계정 연결, 전환 액션 생성
- GA4 방문자/세션 리포트를 개별 또는 전체 프로젝트 일괄 조회, `launchd`로 매주
  자동 실행

**운영 대시보드** (`lens dashboard`, 로컬 정적 HTML, 서버 없음)
- 프로젝트별 상태·PR·GA4 7일 지표를 카드로 한눈에
- 헬스체크 — "방문자 0"이 트래픽이 없는 건지 사이트가 죽은 건지 구분
- GA4 요약 표(트래픽 많은 순), 합계 방문자/세션
- `--serve`로 로컬 서버를 띄우면 페이지 안의 "새로고침" 버튼으로 최신 데이터를
  다시 불러올 수 있음(터미널로 안 돌아가도 됨)

**코드/보안 감사**
- `lens readme-audit` — README 없음/스캐폴드 기본값 그대로/내용 부족을 분류
- `lens license-audit` — GitHub의 라이선스 인식 결과 기준
- `lens vuln-audit` — GitHub Dependabot 알림(꺼져 있는 저장소는 별도로 표시)

**수익화 (AdSense)**
- 프로젝트별 광고 게재 정책(`allowed`/`excluded`/`unreviewed`) 관리 — 새로 등록된
  프로젝트는 기본적으로 광고 대상에서 제외됨
- `ads.txt`를 프레임워크에 맞는 위치에 자동 배치
- GTM에 AdSense 연결 스크립트를 Custom HTML 태그로 추가(앱 소스 코드는 안 건드림)

**Cloudflare DNS/Tunnel**
- API 토큰 등록(OS 키체인), 새 서브도메인을 Cloudflare Tunnel + DNS에 라우팅

## 지원하는 배포 방식

| 배포 방식 | 감지 기준 | 비고 |
|---|---|---|
| Cloudflare Workers / Pages | `wrangler.toml`/`.jsonc`, `package.json`의 `wrangler` 의존성 | 정적 HTML, Docusaurus, Astro Starlight, Next.js App Router, SvelteKit 전부 지원 |
| Vercel | `vercel.json` | 위와 동일한 삽입 전략 공유(`adapters/_static_site.py`) |
| GitHub Pages | 배포 워크플로 존재 | 위와 동일 |
| oh-my-homelab (K8s + ArgoCD) | `deploy/charts/` 디렉터리 | 레포별 전용 패치 우선 시도, 실패하면 Next.js App Router 범용 폴백 |

## 빠른 시작

```bash
uv venv .venv && uv pip install -e . --python .venv/bin/python  # 최초 1회

lens creds check                                    # 인증 상태 확인 (docs/SECURITY.md)
lens project add https://github.com/org/repo --metadata-only --site-url https://example.com
lens track sync <slug>                              # 기본은 dry-run, --yes로 실제 진행
lens dashboard                                       # 등록된 전체 프로젝트 상태 보기
```

## 명령어

| 그룹 | 명령어 | 설명 |
|---|---|---|
| `lens project` | `add` / `list` / `show` / `set-site-url` / `set-ads-policy` | 레지스트리 등록·조회, 배포 URL/광고 정책 설정 |
| `lens track` | `sync` / `link-ads` / `report` / `report-all` | GA4/GTM 자동 세팅, Ads 연결, 성과 리포트 |
| `lens creds` | `init` / `check` / `accounts` / `set-accounts` / `map-org` | Google/Cloudflare 인증, 다중 계정 프로필 |
| `lens cloudflare` | `tunnel-route` | 새 서브도메인을 DNS + Tunnel에 라우팅 |
| `lens ads-sync` | — | `ads.txt` 배치 + GTM AdSense 태그 일괄 적용 |
| `lens adsense-status` | — | 연결된 AdSense 계정/사이트 승인 상태 조회 |
| `lens dashboard` | — | 로컬 대시보드 생성(`--serve`로 새로고침 가능) |
| `lens readme-audit` / `license-audit` / `vuln-audit` | — | 등록된 프로젝트 전체를 문서/라이선스/취약점 기준으로 점검 |
| `lens logs show <run_id>` | — | 특정 실행의 상세 로그와 에러 힌트 |

각 명령어의 세부 옵션은 `lens <명령어> --help`로 확인하세요. Claude Code 슬래시
커맨드 ↔ CLI 매핑은 [`docs/COMMANDS.md`](docs/COMMANDS.md) 참고.

## 문서

전체 문서 목록과 각 문서가 다루는 범위는 [`docs/README.md`](docs/README.md)에
정리되어 있습니다. 자주 찾게 되는 것들:

- [`docs/SECURITY.md`](docs/SECURITY.md) — 자격증명 보관·설정 매뉴얼
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 전체 구조와 컴포넌트
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — 에러 타입별 원인·해결 절차
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — 배포 방식별 어댑터 명세

## 상태

이 프로젝트는 개인적으로 운영 중인 20개 이상의 프로젝트에 실사용 중입니다. 진행
이력은 [`docs/ROADMAP.md`](docs/ROADMAP.md)에 Phase별로 기록되어 있습니다.
