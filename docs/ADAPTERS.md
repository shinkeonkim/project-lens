# 배포 어댑터 명세

배포 어댑터는 "레포를 감지하고, 트래킹 코드를 삽입하고, 배포한다"는 3단계 책임만 가집니다.
공통 인터페이스는 [`ARCHITECTURE.md`](ARCHITECTURE.md#4-deployment-adapters) 참고.

## CloudflareWorkersAdapter

### detect()

다음 중 하나라도 있으면 매치:

- `wrangler.toml` 또는 `wrangler.jsonc` / `wrangler.json` 존재
- `package.json`의 `devDependencies`/`dependencies`에 `wrangler` 포함

### inject_tracking()

REQUEST.md 대상 레포들은 대부분 정적 사이트를 Cloudflare Workers로 서빙하는 구조로 추정되므로,
1차 구현은 아래 우선순위로 삽입 지점을 탐색합니다.

1. 정적 HTML 엔트리(`index.html`, `public/index.html`, `dist/index.html` 등)가 있으면
   `<head>` 최상단에 GTM 스니펫, `<body>` 시작 직후에 noscript iframe 삽입
2. 프레임워크 기반(Next.js/Astro 등)이면 프레임워크 관례에 맞는 삽입 지점 사용
   (예: Next.js `app/layout.tsx` 또는 `_document.tsx`에 `<Script>` 컴포넌트 추가)
3. 위 둘 다 아니면(Workers가 직접 HTML을 생성/응답하는 구조) 응답 생성 함수에서 GTM 컨테이너
   ID를 환경 변수(`wrangler.toml`의 `[vars]` 또는 `wrangler secret`)로 주입하고, 코드가 응답
   HTML에 스니펫을 문자열로 삽입하도록 최소 diff 패치

삽입 지점이 자동으로 특정되지 않는 레포는 `AdapterDetectionError`를 발생시키지 않고, "수동 삽입
필요" 상태로 `needs_attention` 처리 + PR 대신 이슈(diff 제안 포함)를 생성합니다 — 무리하게 추측한
코드 수정을 강제로 커밋하지 않기 위함입니다.

### deploy()

- 기본(`pr`): 브랜치 생성 → 커밋 → `gh pr create`
- 옵트인(`direct`): PR 생성 후 곧바로 `wrangler deploy --env <project 설정>` 실행. Cloudflare
  API 토큰은 [`SECURITY.md`](SECURITY.md)에 따라 로컬에만 보관되어 있어야 하며, 없으면
  `direct` 모드는 자동으로 `pr` 모드로 폴백하고 경고를 남깁니다.

### 적용 대상 (REQUEST.md 기준)

kokoa-lab: how-to-get-google-dot-com, dice-art, pattern-type, dev-tarot, review-slot,
please-delete-my-account, cozy-hive
kokoa-study-room: transaction-isolation-level, compiler-study-site,
terraform-associate-004-study-notes
shinkeonkim: my-portfolio, my-cv, my-resume

## OhMyHomelabAdapter

`oh-my-homelab`은 개인 홈서버에서 여러 서비스를 배포하는 자체 도구로, 아직 이 저장소의 배포
관례(compose 구조, 서비스 등록 방식, 환경 변수 규약 등)를 조사하지 않았습니다. 따라서 이
어댑터는 **설계만 확정하고 구현은 Phase 4로 미룹니다** (자세한 사유는 [`ROADMAP.md`](ROADMAP.md)).

### detect() — 잠정안 (조사 후 확정 필요)

`shinkeonkim/oh-my-homelab`의 서비스 등록 방식을 조사해 아래 중 실제 패턴을 확인합니다.

- 레포 루트에 homelab 전용 매니페스트(예: `homelab.yaml`, `.homelab/`) 존재
- 또는 `docker-compose.yml`에 homelab 특유의 라벨/네이밍 규약 존재

### inject_tracking() — 잠정안

컨테이너 기반 배포로 추정되므로, 정적 HTML 삽입보다는 **환경 변수로 GTM ID를 주입**하고 애플리케이션
코드가 이를 읽어 스니펫을 렌더링하는 방식을 우선 검토합니다. `codekr` 레포의 실제 스택(정적 사이트
생성기인지, 서버 렌더링인지)을 조사한 뒤 CloudflareWorkersAdapter와 동일하게 "삽입 지점 자동 특정
불가 시 이슈로 대체" 원칙을 적용합니다.

### deploy() — 잠정안

oh-my-homelab의 배포 트리거 방식(예: git push 기반 GitOps, 또는 별도 CLI/webhook)을 조사해
`direct` 모드에서 무엇을 실행할지 확정합니다. 확정 전까지는 `pr` 모드만 지원.

### 적용 대상

shinkeonkim/codekr (배포 도구: shinkeonkim/oh-my-homelab)

## 새 어댑터 추가 시 체크리스트

1. `detect()`가 다른 어댑터와 겹치지 않는지 확인 (겹치면 등록 순서로 우선순위 결정되므로 명시적 테스트 필요)
2. `inject_tracking()`은 항상 diff(ChangeSet)를 반환하고, 실제 커밋은 CLI 상위 레이어에서 수행
   (어댑터가 git 오퍼레이션을 직접 하지 않도록 책임 분리)
3. 삽입 지점을 확신할 수 없는 케이스에 대한 폴백(이슈 생성)을 반드시 구현
4. `direct` 배포에 필요한 자격증명이 없을 때의 폴백 동작을 정의
