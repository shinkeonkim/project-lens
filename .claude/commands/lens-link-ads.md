---
description: 프로젝트의 GA4 속성을 Google Ads 계정과 연결하고, 가능하면 전환 액션도 만듭니다
---

`$ARGUMENTS`에서 프로젝트 slug와 연결할 Google Ads customer ID(하이픈 없이 숫자만, 예:
`1112223333`)를 파악하세요. slug를 모르면 `/lens-list`로 먼저 확인하세요.

**사전 조건**: 이 프로젝트에 GA4 속성이 이미 있어야 합니다 (`/lens-sync`를 먼저 실행해야
함). Developer Token이 등록돼 있지 않으면 GA4-Ads 연결만 하고 전환 액션 생성은
건너뜁니다 — 이는 오류가 아니라 정상 동작입니다.

1. project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
   먼저 dry-run을 실행하세요:

   ```
   lens track link-ads <SLUG> --customer-id <CUSTOMER_ID>
   ```

2. 계획(GA4-Ads 연결 여부, 전환 액션 생성 여부)을 보여주고 진행 여부를 확인받으세요 —
   실제 Google Ads 계정에 연결되는 되돌리기 번거로운 작업입니다.
3. 확인받으면 `--yes`를 추가해 실행하세요.
4. 결과(연결된 GA4-Ads 링크, 생성된 전환 액션 리소스 이름)를 보여주세요.

실패 시 에러를 그대로 보여주고, GA4 속성이 없다는 오류면 `/lens-sync`를 먼저 실행하라고
안내하세요.
