# Claude Code 커맨드 명세

각 커맨드는 `.claude/commands/lens-*.md`로 정의되며, Claude가 사용자의 자연어 요청을 해석해
`lens` CLI를 Bash 도구로 호출하고 결과를 요약합니다. 커맨드 자체는 로직을 갖지 않고 CLI를
얇게 감싸는 역할만 합니다 — 판단/부수효과는 전부 CLI(Python) 쪽에 있습니다.

## 커맨드 목록

| 커맨드 | CLI 매핑 | 설명 |
|---|---|---|
| `/lens-add-project <github_url> [--deploy-type=cloudflare_workers\|oh_my_homelab]` | `lens project add <url> [...]` | 신규 프로젝트 등록 + 최초 트래킹 세팅(GA4/GTM 생성, 스니펫 삽입, PR 생성) |
| `/lens-sync <slug>` | `lens track sync <slug>` | 기존 트래킹 설정 재검증/재동기화 (drift 감지, 필요 시 재삽입) |
| `/lens-status [slug]` | `lens project status [slug]` | 프로젝트별 상태(마지막 동기화, GA4 수신 여부, 배포 상태) 표시 |
| `/lens-list` | `lens project list` | 전체 등록 프로젝트를 표 형태로 출력 |
| `/lens-remove <slug>` | `lens project remove <slug>` | soft delete (status=`archived`), 이력은 보존 |
| `/lens-report <slug> [--range=7d\|30d]` | `lens track report <slug> --range ...` | GA4/Ads 성과 지표 요약 (방문자수, 전환율, CTR, 광고비 등) |
| `/lens-creds-setup` | `lens creds check` / 대화형 안내 | `credentials_meta` 상태 점검, 누락/만료 항목에 대한 [`SECURITY.md`](SECURITY.md) 절차 안내 |
| `/lens-logs <run_id>` | `lens logs show <run_id>` | 실행 로그 + 에러 타입별 문제 해결 가이드 출력 |

## 설계 원칙

- **하나의 커맨드 = 하나의 CLI 서브커맨드 호출.** 커맨드 마크다운 안에서 여러 단계를 순차
  실행하지 않습니다(재시도/부분 실패 처리를 프롬프트 로직에 맡기면 신뢰할 수 없음) — 여러 단계가
  필요한 워크플로우는 CLI 내부에서 하나의 트랜잭션처럼 처리하고 마지막에 요약만 반환합니다.
- **모든 상태 변경 커맨드는 실행 전 요약을 먼저 보여주고 진행 여부를 확인**합니다
  (예: "kokoa-lab/dice-art에 GTM 컨테이너를 새로 만들고 PR을 생성합니다. 진행할까요?").
  이는 Claude Code 레벨의 실행 확인과 별개로, CLI가 `--yes` 없이는 dry-run 결과만 출력하고
  종료하는 방식으로 구현합니다.
- **실패는 항상 사람이 읽을 수 있는 다음 행동과 함께 보고**합니다. CLI가 원시 스택트레이스를
  그대로 뱉지 않고, 에러 타입에 맞는 요약 + `docs/TROUBLESHOOTING.md` 링크를 함께 반환합니다.
- **직접 배포(`deploy_mode=direct`)는 별도 명시 없이는 절대 트리거되지 않습니다.** 기본은 PR
  생성이며, 사용자가 프로젝트 등록 시 `--deploy-mode=direct`를 명시했을 때만 CLI가 실제 배포
  단계(`wrangler deploy` 등)를 수행합니다.

## 예시 세션

```
사용자: dice-art 레포에 트래킹 세팅해줘. https://github.com/kokoa-lab/dice-art

Claude: (내부적으로 `lens project add https://github.com/kokoa-lab/dice-art --dry-run` 실행)
  다음 작업을 진행합니다:
  - GA4 속성 "dice-art" 생성 (계정: shinkeonkim 기본 계정)
  - GTM 컨테이너 생성 + 기본 GA4 Configuration Tag/클릭 트리거 추가
  - Cloudflare Workers 어댑터로 감지됨 → HTML 템플릿에 GTM 스니펫 삽입
  - `feat/add-tracking` 브랜치에 커밋 후 PR 생성 (직접 배포 아님)
  진행할까요?

사용자: 응 진행해줘

Claude: (`lens project add https://github.com/kokoa-lab/dice-art --yes` 실행)
  완료했습니다.
  - GA4: G-XXXXXXX
  - GTM: GTM-XXXXXXX (게시됨)
  - PR: https://github.com/kokoa-lab/dice-art/pull/12
  - run_id: 42 (문제 있으면 `/lens-logs 42`)
```
