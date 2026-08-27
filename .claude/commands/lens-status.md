---
description: 프로젝트 하나의 등록 상세 정보를 보여줍니다 (Phase 0 - 동기화/배포 상태 점검은 미구현)
---

**중요**: `docs/COMMANDS.md`에 설계된 `/lens-status`는 최종적으로 마지막 동기화 시각,
GA4 수신 여부, 배포 상태까지 보여줄 예정이지만, 아직 Phase 0 단계라 그런 헬스체크는
구현되어 있지 않습니다. 지금은 레지스트리에 저장된 메타데이터만 보여줄 수 있습니다.

`$ARGUMENTS`에서 프로젝트 slug를 파악하세요 (예: `kokoa-lab-dice-art`). slug를 모르겠다면
먼저 `/lens-list`로 전체 목록을 보여주고 사용자에게 확인받으세요.

project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
다음을 실행하세요:

```
lens project show <SLUG>
```

결과를 사람이 읽기 좋은 형태로 요약하세요. slug가 존재하지 않으면 에러 메시지를 그대로
보여주고 `/lens-list`로 정확한 slug를 확인하라고 안내하세요.
