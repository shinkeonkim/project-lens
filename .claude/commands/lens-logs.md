---
description: 특정 실행(run_id)의 상세 로그와 문제 해결 힌트를 보여줍니다
---

`$ARGUMENTS`에서 run_id(정수)를 파악하세요. 모르면 `/lens-status <slug>`로 최근 실행의
run_id를 먼저 확인하도록 안내하세요.

project-lens 레포 루트에서 `lens`(PATH에 없으면 `<project-lens repo>/.venv/bin/lens`)로
다음을 실행하세요:

```
lens logs show <RUN_ID>
```

- 성공한 실행이면 결과(PR/이슈 링크, 커밋 SHA)를 요약해서 보여주세요.
- 실패한 실행이면 `error_code`/`error_summary`와 함께 출력되는 힌트를 보여주고,
  `docs/TROUBLESHOOTING.md`의 해당 에러 타입 섹션을 참고해 구체적인 다음 행동을
  안내하세요 (예: `AuthError`면 `/lens-creds-setup` 다시 실행).
- run_id가 존재하지 않으면 `/lens-status <slug>`로 정확한 run_id를 확인하라고 안내하세요.
