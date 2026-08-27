# project-lens

여러 웹사이트 프로젝트의 Google Analytics(GA4) / Google Tag Manager(GTM) / Google Ads 트래킹 설정을
일관되게 등록·배포·관리하기 위한 도구입니다. Claude Code 커스텀 커맨드를 통해 조작하며,
실제 로직은 Python CLI(`lens`)와 로컬 SQLite 레지스트리가 담당합니다.

## 왜 필요한가

- 개인/스터디/랩에서 운영 중인 웹사이트가 여러 개이고, 배포 방식(Cloudflare Workers, oh-my-homelab)도 제각각입니다.
- 사이트마다 GA4 속성, GTM 컨테이너, Ads 전환 액션을 손으로 만들면 누락·불일치가 생기기 쉽습니다.
- 작업할 때만 레포를 clone하고 끝나면 삭제하여 로컬에 여러 프로젝트 코드를 쌓아두지 않아야 합니다.
- 어떤 프로젝트를 언제 어떻게 세팅했는지 기록이 남아야 재작업·비교·감사(audit)가 가능합니다.

## 현재 상태

Phase 0~5(`docs/ROADMAP.md`)를 실사용 검증까지 완료했습니다.

- 등록된 14개 레포 전부 GTM 스니펫 삽입 계획이 있음을 확인(정적 HTML 11개, Docusaurus 1개,
  Astro Starlight 1개, Next.js/oh-my-homelab 1개)
- 실제로 GA4 속성 + GTM 컨테이너를 자동 생성하고 PR을 만든 사례:
  [shinkeonkim/my-portfolio#1](https://github.com/shinkeonkim/my-portfolio/pull/1),
  [shinkeonkim/codekr#667](https://github.com/shinkeonkim/codekr/pull/667)
- 남은 일: Google Ads Developer Token 승인 대기(라이브 검증 전), `/lens-report`(성과 리포트) 미착수

## 빠른 시작

```bash
uv venv .venv && uv pip install -e . --python .venv/bin/python  # 최초 1회
.venv/bin/lens project add https://github.com/org/repo --metadata-only
.venv/bin/lens creds check          # Google 인증 상태 확인 (docs/SECURITY.md)
.venv/bin/lens track sync <slug>    # 기본은 dry-run, --yes로 실제 진행
```

Claude Code 안에서는 CLI 대신 `/lens-add-project`, `/lens-sync`, `/lens-status` 같은
슬래시 커맨드를 씁니다 (`.claude/commands/`, [`docs/COMMANDS.md`](docs/COMMANDS.md) 참고).

## 문서

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 전체 구조, 컴포넌트, 워크플로우
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — SQLite 레지스트리 스키마
- [`docs/COMMANDS.md`](docs/COMMANDS.md) — Claude Code 커맨드 ↔ CLI 서브커맨드 매핑
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — 배포 방식별 어댑터(Cloudflare Workers / oh-my-homelab) 명세
- [`docs/SECURITY.md`](docs/SECURITY.md) — 자격증명 보관·설정 매뉴얼
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — 에러 타입별 원인·해결 절차
- [`docs/GOOGLE_ADS_GUIDE.md`](docs/GOOGLE_ADS_GUIDE.md) — Google Ads Developer Token 신청부터 연동까지 단계별 매뉴얼
- [`docs/SCHEDULED_REPORTS.md`](docs/SCHEDULED_REPORTS.md) — launchd로 매주 GA4 리포트 자동 실행하기
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — 단계별 구현 계획과 진행 상황

## 추적 대상 (REQUEST.md 기준)

Cloudflare Workers 배포:

- kokoa-lab/how-to-get-google-dot-com, dice-art, pattern-type, dev-tarot, review-slot,
  please-delete-my-account, cozy-hive
- kokoa-study-room/transaction-isolation-level, compiler-study-site, terraform-associate-004-study-notes
- shinkeonkim/my-portfolio, my-cv, my-resume

oh-my-homelab 배포:

- shinkeonkim/codekr (참고: shinkeonkim/oh-my-homelab)
