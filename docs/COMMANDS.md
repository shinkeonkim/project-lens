# Claude Code 커맨드 명세

각 커맨드는 `.claude/commands/lens-*.md`로 정의되며, Claude가 사용자의 자연어 요청을 해석해
`lens` CLI를 Bash 도구로 호출하고 결과를 요약합니다. 커맨드 자체는 로직을 갖지 않고 CLI를
얇게 감싸는 역할만 합니다 — 판단/부수효과는 전부 CLI(Python) 쪽에 있습니다.

## 커맨드 목록

`구현` 열이 없는 행은 아직 CLI 쪽 기능이 없어 커맨드 파일도 만들지 않은 상태입니다
(계획만 있음). docs/ROADMAP.md에서 어느 Phase에 해당하는지 확인하세요.

| 커맨드 | CLI 매핑 | 설명 | 구현 |
|---|---|---|---|
| `/lens-add-project <github_url> [--deployment-type=...] [--site-url=...]` | `lens project add <url> --metadata-only [...]` | 신규 프로젝트를 레지스트리에 등록 (메타데이터만 — 트래킹 세팅은 `/lens-sync`에서) | ✅ Phase 0 |
| `/lens-sync <slug> [--gtm-id=...]` | `lens track sync <slug> [--gtm-id ...] [--yes]` | GTM 스니펫 삽입 + PR 생성. `--gtm-id` 생략 시 GA4/GTM API로 자동 프로비저닝 | ✅ Phase 1-2 |
| `/lens-link-ads <slug> --customer-id=...` | `lens track link-ads <slug> --customer-id ... [--yes]` | GA4 속성을 Google Ads 계정과 연결하고, Developer Token이 있으면 전환 액션도 생성 | ✅ Phase 3 (라이브 미검증) |
| `/lens-status <slug>` | `lens project show <slug>` | 프로젝트 등록 메타데이터 + 가장 최근 실행(PR/이슈 링크, 실패 시 에러) 표시 | ✅ Phase 0, 5 |
| `/lens-list` | `lens project list` | 전체 등록 프로젝트를 표 형태로 출력 | ✅ Phase 0 |
| `/lens-creds-setup` | `lens creds check` / `init` / `accounts` / `set-accounts` | Google/Ads 자격증명 상태 점검, 누락 항목에 대한 [`SECURITY.md`](SECURITY.md) 절차 안내 | ✅ Phase 2-3 |
| `/lens-logs <run_id>` | `lens logs show <run_id>` | `deploy_runs` 실행 1건의 상세 + 에러 타입별 [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) 힌트 출력 | ✅ Phase 5 |
| `/lens-report <slug> [--range=7d\|30d]` | `lens track report <slug> --range ...` | GA4 방문자/세션/이탈률 + (연결 시) Ads 노출/클릭/CTR/비용/전환 요약. 읽기 전용 | ✅ Phase 3, 6 |
| `/lens-remove <slug>` | `lens project remove <slug>` | soft delete (status=`archived`), 이력은 보존 | ⏳ 미구현 |

### CLI 전용 (아직 슬래시 커맨드 없음)

아래는 `lens` CLI로만 쓸 수 있습니다 — 자주 쓰게 되면 그때 커맨드 파일을 추가할 것.

| CLI | 설명 |
|---|---|
| `lens project set-ads-policy <slug> <allowed\|excluded\|unreviewed>` | 프로젝트별 광고(AdSense) 게재 정책 설정 |
| `lens track report-all [--range=7d\|30d]` | 등록된 전체 프로젝트의 GA4 리포트를 일괄 조회, 개별 실패해도 계속 진행 |
| `lens dashboard [--serve] [--offline]` | 로컬 대시보드 생성/서빙(헬스체크, GA4 요약, PR 상태) |
| `lens readme-audit` / `license-audit` / `vuln-audit` | 등록된 프로젝트 전체를 README/라이선스/Dependabot 취약점 기준으로 점검 |
| `lens ads-sync --publisher-id <ID> [--yes]` | `ads_policy=allowed`인 프로젝트에 `ads.txt` + GTM AdSense 태그 일괄 적용 |
| `lens adsense-status` | 연결된 AdSense 계정/사이트 승인 상태 조회 |
| `lens cloudflare tunnel-route <hostname> <service>` | 새 서브도메인을 Cloudflare DNS + Tunnel에 라우팅 |
| `lens creds init --provider cloudflare --token <TOKEN>` | Cloudflare API 토큰을 OS 키체인에 저장 |

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
