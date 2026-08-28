# 문서 색인

주제별로 정리했습니다. 처음 설정할 땐 **시작하기** 순서대로, 이후엔 필요한 걸
바로 찾아보면 됩니다.

## 시작하기

1. [`SECURITY.md`](SECURITY.md) — Google/Cloudflare 자격증명 발급·저장 절차. 가장
   먼저 필요합니다.
2. 최상위 [`README.md`](../README.md)의 "빠른 시작" — 첫 프로젝트 등록부터
   `lens track sync`까지.
3. [`COMMANDS.md`](COMMANDS.md) — Claude Code 슬래시 커맨드(`/lens-*`)와 CLI
   서브커맨드의 대응 관계.

## 구조 이해하기

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — 레이어 구성, 컴포넌트 책임 분리.
- [`DATA_MODEL.md`](DATA_MODEL.md) — SQLite 레지스트리 스키마(`~/.project-lens/registry.sqlite3`).
  민감정보를 저장하지 않는 이유도 여기 있습니다.
- [`ADAPTERS.md`](ADAPTERS.md) — 배포 방식(Cloudflare Workers/Vercel/GitHub
  Pages/oh-my-homelab)별 감지·삽입 전략.

## 기능별 매뉴얼

- [`GOOGLE_ADS_GUIDE.md`](GOOGLE_ADS_GUIDE.md) — Google Ads Developer Token
  신청부터 GA4 연결까지.
- [`SCHEDULED_REPORTS.md`](SCHEDULED_REPORTS.md) — `launchd`로 매주 GA4 리포트
  자동 실행하기.

## 운영 중 참고

- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — 에러 타입(`errors.py`)별 원인과
  해결 절차. `오류: ...`가 나오면 먼저 여기를 찾아보세요.
- [`ROADMAP.md`](ROADMAP.md) — Phase별 구현 이력과 실제로 겪은 문제들.

## 이 저장소엔 없는 것

`docs/private/`(gitignored)에는 실제로 추적 중인 프로젝트 목록·도메인·GA4/GTM ID를
정리한 로컬 전용 문서가 있습니다 — 비밀값은 아니지만 공개 저장소에 두기엔 정보가
너무 구체적이라 뺐습니다. 필요하면 로컬에서 직접 열어보세요.
