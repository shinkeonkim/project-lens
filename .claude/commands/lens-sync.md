---
description: 프로젝트에 GTM 트래킹 스니펫을 삽입하고 PR을 생성합니다 (GA4/GTM 자동 프로비저닝 포함)
---

`$ARGUMENTS`에서 프로젝트 slug(예: `kokoa-lab-dice-art`, `/lens-list`로 확인 가능)와,
사용자가 이미 알고 있는 기존 GTM 컨테이너 ID를 언급했다면 그것도 파악하세요.

1. project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
   먼저 **dry-run**을 실행하세요 (`--yes` 없이):

   ```
   lens track sync <SLUG> [--gtm-id <GTM_ID>]
   ```

   - `--gtm-id`를 생략하면 GA4 속성/GTM 컨테이너를 API로 자동 생성 또는 조회합니다
     (사전에 `/lens-creds-setup`이 완료되어 있어야 함).
   - `--gtm-id`를 지정하면 기존 컨테이너에 스니펫만 삽입합니다.

2. dry-run 결과(변경될 파일, 생성될 GA4/GTM 리소스 여부, 브랜치/PR 계획)를 사람이 읽기
   좋게 요약해서 보여주고, 실제로 진행할지 사용자에게 확인받으세요. 이 작업은 실제
   GitHub PR과 (자동 모드라면) 실제 GA4/GTM 리소스를 만드는 **되돌리기 번거로운 작업**이므로
   반드시 확인 후 진행하세요.
3. 확인받으면 같은 명령에 `--yes`를 추가해 실행하세요.
4. 결과(PR 링크 또는 이슈 링크, GTM/GA4 ID)를 보여주세요. 삽입 지점을 못 찾으면 대신
   GitHub 이슈가 생성됩니다 — 그 경우 수동 조치가 필요하다는 점을 안내하세요.

실패 시 에러 메시지를 그대로 보여주고, `AuthError`/`ValidationError`면
`/lens-creds-setup`이나 `lens project set-site-url`이 먼저 필요할 수 있다고 안내하세요.
