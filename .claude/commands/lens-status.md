---
description: 프로젝트 하나의 등록 정보와 가장 최근 실행 이력을 보여줍니다
---

`$ARGUMENTS`에서 프로젝트 slug를 파악하세요 (예: `kokoa-lab-dice-art`). slug를 모르겠다면
먼저 `/lens-list`로 전체 목록을 보여주고 사용자에게 확인받으세요.

project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
다음을 실행하세요:

```
lens project show <SLUG>
```

레지스트리 메타데이터(등록 정보, site_url 등)와 함께 "최근 실행" 섹션이 나옵니다:

- 성공(`success`)이면 PR 링크와 요약을 보여주세요.
- 실행 기록이 없으면 아직 `/lens-sync`를 실행한 적이 없다는 뜻입니다 — 안내하세요.
- 실패(`failed`)면 에러 타입과 요약이 함께 나옵니다. run_id를 알려주고, 더 자세히 보려면
  `/lens-logs <run_id>`를 쓸 수 있다고 안내하세요.

slug가 존재하지 않으면 에러 메시지를 그대로 보여주고 `/lens-list`로 정확한 slug를
확인하라고 안내하세요.
