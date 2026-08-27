---
description: GitHub 레포를 project-lens 레지스트리에 등록합니다 (Phase 0 - 메타데이터 등록만)
---

사용자가 등록하려는 GitHub 레포 URL을 `$ARGUMENTS`에서 파악하세요. 배포 방식을
언급했다면(Cloudflare Workers / oh-my-homelab) `--deployment-type`으로 함께 전달하고,
언급이 없으면 생략하세요(기본값 `unknown`).

**중요**: 이 도구는 아직 Phase 0 단계입니다. 트래킹 자동 세팅(GA4/GTM 생성, 스니펫 삽입,
PR 생성)은 구현되어 있지 않습니다 — 이 커맨드는 레지스트리에 메타데이터만 등록합니다.
사용자가 "GTM/GA 설정까지 해달라"고 요청하면, 아직 지원되지 않는다고 명확히 안내하세요.

1. project-lens 레포 루트에서 `lens` 실행 파일을 찾습니다 (PATH에 있으면 `lens`,
   없으면 `<project-lens repo>/.venv/bin/lens`).
2. 다음 커맨드를 실행합니다:

   ```
   lens project add <GITHUB_URL> --metadata-only [--deployment-type cloudflare_workers|oh_my_homelab]
   ```

3. 성공하면 등록된 slug/visibility/deployment_type/status를 요약해서 보여주세요.
4. 실패하면(인증 안 됨, 접근 권한 없음, URL 형식 오류 등) 에러 메시지를 그대로 보여주고,
   `AuthError`면 `gh auth login`을, `RepoAccessError`면 조직 접근 권한 확인을 안내하세요
   (자세한 절차는 `docs/SECURITY.md` 참고).
