# 문제 해결 가이드

`lens` 명령이 실패하면 `오류: ...` 형태로 에러 메시지를 출력합니다(`src/project_lens/cli.py`
`_entrypoint`). `--yes`로 실행하다 실패한 경우 `deploy_runs`에 실행 기록이 남으므로
`lens logs show <run_id>`로 다시 확인할 수 있습니다. 아래는 에러 타입(`errors.py`)별
원인과 대처입니다 — 괄호 안은 이 프로젝트를 실제로 만들면서 겪은 사례입니다.

## AuthError

**의미**: GitHub(`gh`) 또는 Google 인증이 안 되어 있거나 만료됨.

- `gh CLI가 로그인되어 있지 않습니다` → `gh auth login`
- `Google 인증 정보가 없습니다` → `lens creds init --provider google`
- `Google Ads Developer Token이 없습니다` → `lens creds init --provider google-ads --developer-token ...`

**스코프 부족으로 인한 재인증** (실제로 두 번 겪음): `google/auth.py`의 `SCOPES`에 새 항목을
추가할 때마다(GTM 워크스페이스 게시 권한 추가, Ads `adwords` 스코프 추가 등), **기존에
저장된 credentials는 그 스코프를 갖고 있지 않습니다.** 이 상태에서 `load_credentials()`가
토큰을 갱신하려 하면 `google.auth.exceptions.RefreshError: invalid_scope` 또는
`invalid_client`로 실패합니다. 해결책은 항상 같습니다 — `lens creds init --provider google`
재실행(브라우저 재동의). `SCOPES`를 바꾸는 코드 변경을 만들 때마다 이 재인증이 필요하다는
점을 사용자에게 미리 안내하세요.

## RepoAccessError

**의미**: GitHub 레포 조회/clone/push가 실패함.

- 레포가 존재하지 않거나 URL 오타 → URL 재확인
- private 레포인데 조직 접근 권한이 없음 → `gh auth status`에서 해당 조직에 대한 SSO/접근
  승인이 됐는지 확인 (`docs/SECURITY.md` 1번 섹션)
- clone 실패인데 위 둘 다 아니면 → 네트워크 문제나 GitHub 장애일 수 있음, 잠시 후 재시도

## AdapterDetectionError

**의미**: 등록된 어댑터(`CloudflareWorkersAdapter`, `OhMyHomelabAdapter`) 중 어느 것도
`detect()`가 `True`를 반환하지 않음.

- 프로젝트를 등록할 때 지정한 `deployment_type`이 실제와 다를 수 있습니다 — 실제로
  `kokoa-study-room/compiler-study-site`가 이 문제였습니다(등록은 `cloudflare_workers`가
  맞았지만, 어댑터가 레포 루트만 보고 서브디렉터리 안의 `wrangler.jsonc`를 못 찾음 —
  `docs/ROADMAP.md` Phase 5에서 서브디렉터리 탐색을 추가해 해결).
- 정말 지원하지 않는 배포 방식이면(`docs/ADAPTERS.md` 참고) 새 어댑터를 만들어야 합니다.

## 삽입 지점을 못 찾음 (change_set이 None — 예외가 아니라 이슈 생성으로 처리됨)

어댑터가 `detect()`는 통과했지만 `inject_tracking()`이 알려진 삽입 지점을 못 찾으면
예외를 던지지 않고 `None`을 반환합니다. `--yes`면 CLI가 GitHub 이슈를 만들고 프로젝트를
`needs_attention`으로 표시합니다. `lens project show <slug>`로 어떤 이슈가 만들어졌는지
확인하세요(`최근 실행` 섹션의 summary에 이슈 URL이 있습니다).

- 정적 HTML(`index.html` 등)도 없고, Docusaurus/Starlight 설정도 아니면 → 지원하지 않는
  프레임워크입니다. 수동으로 삽입하거나, 패턴이 재사용 가능하면 어댑터를 확장하세요
  (`docs/ADAPTERS.md`의 Docusaurus/Starlight 사례가 참고할 만한 전례입니다).

## GoogleAPIError

**의미**: GA4 Admin API / Tag Manager API / Google Ads API 호출이 실패함.

- **API 계약을 문서/추측만으로 예측하면 실제와 다를 수 있습니다** — 이 프로젝트에서 실제로
  2번 겪었습니다:
  - `AnalyticsAdminServiceClient.list_properties()`는 `filter=` 직접 키워드 인자를 안 받고
    `request={"filter": ...}` 형태여야 합니다.
  - GTM 컨테이너 버전 생성(`create_version`)에는 `tagmanager.edit.containers`와 별도로
    `tagmanager.edit.containerversions` 스코프가 필요합니다(→ AuthError로 이어짐, 위 참고).
  - **교훈**: Google API 클라이언트 코드를 새로 추가/변경했으면, 실제 계정으로 최소 1회
    라이브 검증하기 전까지는 "완료"로 보지 마세요. 이 저장소의 `google/gtm.py`,
    `google/ga4.py`, `google/ads.py` 테스트는 설치된 패키지의 실제 타입/시그니처를
    `inspect.signature()`로 확인한 뒤 그걸 그대로 쓰는 fake로 작성돼 있습니다 — 같은
    방식을 새 코드에도 적용하세요.
- 계정/권한 문제(`PERMISSION_DENIED`, `403`) → `lens creds accounts`로 실제 접근 가능한
  계정인지 확인, `lens creds set-accounts`로 올바른 계정 ID가 저장돼 있는지 확인.
- Google Ads `INVALID_CUSTOMER_ID` 류 → customer ID는 하이픈 없이 숫자만 (`lens track
  link-ads --customer-id 1112223333`).

## DeployError

**의미**: git/gh 오퍼레이션(브랜치/커밋/push/PR/이슈 생성), 또는
`OhMyHomelabAdapter.configure_remote()`의 `gh variable set`이 실패함.

- push 실패 → 브랜치 이름 충돌(같은 프로젝트를 동시에 두 번 `--yes`로 돌린 경우) 또는 권한
  부족. `deploy_runs`에 브랜치 이름이 `project-lens/add-gtm-tracking-<run_id>`로 run마다
  달라 충돌은 거의 없습니다.
- PR 생성 실패 → 이미 같은 브랜치로 열린 PR이 있는지, base 브랜치(`default_branch`)가
  맞는지 확인.
- `gh variable set` 실패 → 해당 레포에 대한 admin/write 권한이 있는지 확인
  (`gh auth status`의 스코프에 `repo` 포함 여부).

## ValidationError

**의미**: 사용자 입력이나 사전 조건이 부족함 — 대부분 메시지에 다음 명령이 그대로 적혀
있습니다.

- `GA4/GTM 기본 계정이 설정되지 않았습니다` → `lens creds accounts` 후 `lens creds
  set-accounts`
- `site_url이 설정되지 않았습니다` → `lens project set-site-url <slug> <URL>`
- `GA4 속성이 없습니다` (link-ads) → 먼저 `lens track sync <slug> --yes`로 GA4를 만들어야 함
- GitHub URL 형식이 아님 → `https://github.com/org/repo` 형태인지 확인
