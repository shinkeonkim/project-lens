# project-lens

여러 웹사이트 프로젝트의 Google Analytics(GA4) / Google Tag Manager(GTM) / Google Ads 트래킹 설정을
일관되게 등록·배포·관리하기 위한 도구입니다. Claude Code 커스텀 커맨드를 통해 조작하며,
실제 로직은 Python CLI(`lens`)와 로컬 SQLite 레지스트리가 담당합니다.

## 왜 필요한가

- 개인/스터디/랩에서 운영 중인 웹사이트가 여러 개이고, 배포 방식(Cloudflare Workers, oh-my-homelab)도 제각각입니다.
- 사이트마다 GA4 속성, GTM 컨테이너, Ads 전환 액션을 손으로 만들면 누락·불일치가 생기기 쉽습니다.
- 작업할 때만 레포를 clone하고 끝나면 삭제하여 로컬에 여러 프로젝트 코드를 쌓아두지 않아야 합니다.
- 어떤 프로젝트를 언제 어떻게 세팅했는지 기록이 남아야 재작업·비교·감사(audit)가 가능합니다.

## 문서

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 전체 구조, 컴포넌트, 워크플로우
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — SQLite 레지스트리 스키마
- [`docs/COMMANDS.md`](docs/COMMANDS.md) — Claude Code 커맨드 ↔ CLI 서브커맨드 매핑
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — 배포 방식별 어댑터(Cloudflare Workers / oh-my-homelab) 명세
- [`docs/SECURITY.md`](docs/SECURITY.md) — 자격증명 보관·설정 매뉴얼
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — 단계별 구현 계획

## 초기 추적 대상 (REQUEST.md 기준)

Cloudflare Workers 배포:

- kokoa-lab/how-to-get-google-dot-com, dice-art, pattern-type, dev-tarot, review-slot,
  please-delete-my-account, cozy-hive
- kokoa-study-room/transaction-isolation-level, compiler-study-site, terraform-associate-004-study-notes
- shinkeonkim/my-portfolio, my-cv, my-resume

oh-my-homelab 배포:

- shinkeonkim/codekr (참고: shinkeonkim/oh-my-homelab)
