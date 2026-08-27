# 배포 어댑터 명세

배포 어댑터는 "레포를 감지하고, 트래킹 코드를 삽입하고, 배포한다"는 3단계 책임만 가집니다.
공통 인터페이스는 [`ARCHITECTURE.md`](ARCHITECTURE.md#4-deployment-adapters) 참고.

## CloudflareWorkersAdapter

### detect()

레포 루트, 또는 그 바로 아래 서브디렉터리 한 단계(모노레포 스타일, 예: `site/`) 안에
다음 중 하나라도 있으면 매치:

- `wrangler.toml` 또는 `wrangler.jsonc` / `wrangler.json` 존재
- `package.json`의 `devDependencies`/`dependencies`에 `wrangler` 포함

### inject_tracking()

wrangler 프로젝트를 찾은 뒤, 아래 우선순위로 실제 프레임워크에 맞는 삽입 전략을 고릅니다
(전부 실제 레포로 라이브 검증됨 — `docs/ROADMAP.md` Phase 1, 5 참고):

1. **Docusaurus** (`docusaurus.config.ts`/`.js`에 classic preset 존재) — 정적 HTML은 빌드
   산출물일 뿐 소스에 없으므로, 프리셋 옵션에 공식 `googleTagManager: { containerId }`를
   추가한다. (`kokoa-study-room/compiler-study-site`로 검증 — 빌드된 HTML에 스니펫이
   실제로 들어가는 것까지 확인)
2. **Astro Starlight** (`astro.config.mjs`/`.ts`/`.js`에 `starlight(` 통합 호출 존재) —
   Starlight의 공식 `head` 옵션으로 인라인 `<script>` 태그를 추가한다.
   (`kokoa-study-room/terraform-associate-004-study-notes`로 검증)
3. **정적 HTML 엔트리** (`index.html`, `public/index.html`, `src/index.html`) — `<head>`
   최상단에 GTM 스니펫, `<body>` 시작 직후에 noscript iframe 삽입. (11개 레포로 검증)
4. **Next.js 등 그 외 프레임워크** — 지금은 지원하지 않는다. 코드가 아니라 배포 자동화
   레포 쪽에서 배선해야 하는 케이스(예: 빌드 시점에 굳는 값)는 `OhMyHomelabAdapter`처럼
   그 레포 전용으로 별도 구현한다 — 일반화하려 하지 않는다.

어느 것도 못 찾으면 `AdapterDetectionError`를 발생시키지 않고, "수동 삽입 필요" 상태로
`needs_attention` 처리 + PR 대신 이슈(확인한 경로 안내 포함)를 생성합니다 — 무리하게 추측한
코드 수정을 강제로 커밋하지 않기 위함입니다.

### deploy()

- 기본(`pr`): 브랜치 생성 → 커밋 → `gh pr create`
- 옵트인(`direct`): PR 생성 후 곧바로 `wrangler deploy --env <project 설정>` 실행. Cloudflare
  API 토큰은 [`SECURITY.md`](SECURITY.md)에 따라 로컬에만 보관되어 있어야 하며, 없으면
  `direct` 모드는 자동으로 `pr` 모드로 폴백하고 경고를 남깁니다.

### 적용 대상 (REQUEST.md 기준, 전부 dry-run으로 커버리지 확인됨 — Phase 5)

- 정적 HTML: kokoa-lab/how-to-get-google-dot-com, dice-art, pattern-type, dev-tarot,
  review-slot, please-delete-my-account, cozy-hive; kokoa-study-room/transaction-isolation-level;
  shinkeonkim/my-portfolio, my-cv, my-resume
- Docusaurus: kokoa-study-room/compiler-study-site (`site/` 서브디렉터리)
- Astro Starlight: kokoa-study-room/terraform-associate-004-study-notes
shinkeonkim: my-portfolio, my-cv, my-resume

## OhMyHomelabAdapter

`oh-my-homelab`(private)은 Kubernetes + ArgoCD(App-of-Apps GitOps)로 여러 서비스를 배포하는
개인 홈랩 인프라입니다. Cloudflare Workers 어댑터와 성격이 근본적으로 다릅니다 — 정적
사이트에 스니펫을 끼워 넣는 게 아니라, **대상 레포(codekr) 자체의 Next.js 코드에 GTM 배선을
추가하는 작업**입니다. 자세한 조사 내용은 `git log`의 Phase 4 커밋 메시지를 참고하세요.

### 왜 이렇게 됐는가

- `codekr`는 정적 사이트가 아니라 api/web/judge/executor 4개 서비스로 구성된 서비스입니다.
  `web`은 Next.js(App Router)이고, GTM을 넣을 표준적인 방법은 `NEXT_PUBLIC_GTM_ID` 환경변수를
  읽어 루트 레이아웃에 조건부로 렌더링하는 것입니다.
- Next.js는 `NEXT_PUBLIC_*` 값을 **빌드 시점에만** 번들에 굳힙니다(런타임 K8s 환경변수로는
  못 바꿈). `codekr`는 이미 이 제약 때문에 브라우저 전용 값(API 주소 등)을 배포 이미지에
  비워 두고 브라우저가 자기 출처를 쓰게 하는 규칙을 갖고 있습니다(같은 이미지로 공개/내부
  주소를 함께 서비스하기 위함, `apps/web/Dockerfile` 주석 참고).
- 배포는 `oh-my-homelab`(private, ArgoCD `automated: {prune: true, selfHeal: true}` —
  머지되면 곧바로 운영 클러스터에 반영됨)이 아니라 **codekr 자신의 GitHub Actions CI**가
  담당합니다: `main` 머지마다 이미지를 빌드해 GHCR에 push하고, `deploy/charts/codekr/values-release.yaml`에
  커밋 SHA를 적어 ArgoCD가 그걸 읽어가는 구조(GitOps지만 이미지 태그는 codekr 저장소가
  스스로 기록).
- 따라서 GTM ID 값은 Helm/K8s 환경변수가 아니라 **codekr 레포의 GitHub Actions 저장소
  변수(`vars.NEXT_PUBLIC_GTM_ID`)**로 CI 빌드 시점에 주입합니다. `oh-my-homelab`(운영
  클러스터에 자동 반영되는 private 레포)은 전혀 건드리지 않습니다 — 리스크를 codekr(public,
  PR 리뷰 가능) 안에 가둡니다.

### detect()

레포 루트에 `deploy/charts/` 디렉터리가 있으면 매치합니다 (oh-my-homelab의
`docs/service-dev-guide/`가 문서화한 "새 서비스는 자기 레포에 Helm 차트를 둔다" 관례).

### inject_tracking()

CloudflareWorkersAdapter처럼 정규식 기반 범용 패턴이 아니라, 실제로 조사한 `codekr`의
파일 내용에 맞춘 **정확한 문자열 앵커 기반 패치**입니다(`adapters/oh_my_homelab.py`):

1. `apps/web/src/shared/analytics/GoogleTagManager.tsx` — `NEXT_PUBLIC_GTM_ID`가 있을 때만
   렌더링하는 head 스크립트 + noscript 컴포넌트 (신규 파일)
2. `apps/web/src/app/layout.tsx` — 위 컴포넌트를 import하고 `<head>`/`<body>`에 삽입
3. `apps/web/Dockerfile` — `ARG`/`ENV NEXT_PUBLIC_GTM_ID` 추가 (기존 `NEXT_PUBLIC_WS_BASE_URL`
   패턴과 동일)
4. `.env.example` — 새 환경변수 문서화
5. `.github/workflows/ci.yml` — `web` 이미지 빌드에만 `build-args: NEXT_PUBLIC_GTM_ID=...` 추가

앵커 문자열이 하나라도 안 맞으면(레이아웃 파일이 없거나 내용이 달라졌으면) None을 반환해
이슈 생성 폴백으로 넘어갑니다 — 다른 구조를 추측해서 잘못 고치지 않습니다.

값 자체(GTM ID)는 어떤 파일에도 하드코딩하지 않습니다. `configure_remote()`가 `--yes`일
때만 `gh variable set NEXT_PUBLIC_GTM_ID --repo <org>/<repo>`로 실제 값을 설정합니다 —
dry-run에서는 절대 호출되지 않습니다(실제 GitHub 상태를 바꾸는 유일한 지점이라 함부로
호출하면 안 됨).

### deploy()

`pr` 모드만 지원(기본값 그대로). `direct` 모드는 구현하지 않았습니다 — codekr는 CI가 매우
엄격하고(단위/통합 테스트, 샌드박스 라이브 테스트, lint/typecheck 184개 웹 테스트 등)
`main`에 직접 머지하는 것은 이 프로젝트의 배포 관례와도 맞지 않습니다.

### 실사용 검증 완료

`lens track sync shinkeonkim-codekr --yes`로 실제 GA4 속성(`G-NZE9ZMZRZD`)/GTM
컨테이너(`GTM-TP9LLDRJ`) 생성, `NEXT_PUBLIC_GTM_ID` 저장소 변수 설정, PR
[#667](https://github.com/shinkeonkim/codekr/pull/667) 생성까지 end-to-end로 확인했습니다.
PR을 만들기 전 로컬에서 `bun install && bun run lint && bun run typecheck && bun run build && bun test`를
직접 돌려 lint 0 errors, typecheck 통과, 47개 라우트 빌드 성공, 기존 웹 테스트 184개 전부
통과를 확인한 뒤 진행했습니다.

### 적용 대상

shinkeonkim/codekr (배포 도구: shinkeonkim/oh-my-homelab, private — 이 어댑터는 그 레포를
전혀 수정하지 않음)

## 새 어댑터 추가 시 체크리스트

1. `detect()`가 다른 어댑터와 겹치지 않는지 확인 (겹치면 등록 순서로 우선순위 결정되므로 명시적 테스트 필요)
2. `inject_tracking()`은 항상 diff(ChangeSet)를 반환하고, 실제 커밋은 CLI 상위 레이어에서 수행
   (어댑터가 git 오퍼레이션을 직접 하지 않도록 책임 분리)
3. 삽입 지점을 확신할 수 없는 케이스에 대한 폴백(이슈 생성)을 반드시 구현
4. `direct` 배포에 필요한 자격증명이 없을 때의 폴백 동작을 정의
