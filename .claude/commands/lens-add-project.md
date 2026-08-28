---
description: GitHub 레포를 project-lens에 새로 등록하고, 원하면 GA4/GTM 트래킹까지 이어서 설정합니다
---

사용자가 등록하려는 GitHub 레포 URL을 `$ARGUMENTS`에서 파악하세요.

1. **배포 방식 파악.** 사용자가 이미 언급했다면 그대로 쓰고, 아니면 레포를 잠깐 살펴서
   추정하세요(`wrangler.toml`/`wrangler.jsonc` → `cloudflare_workers`, `deploy/charts/`
   디렉터리 존재 → `oh_my_homelab`, `vercel.json` → `vercel`, GitHub Pages용 워크플로
   → `github_pages`). 확신이 안 서면 사용자에게 물어보세요. 모르겠으면
   `--deployment-type`을 생략해도 됩니다(기본값 `unknown`).

2. **실제 배포 URL 파악.** 사용자가 알려줬다면 그대로 쓰세요. 모른다면:
   - GitHub의 `homepageUrl` 필드를 먼저 확인하되, **그 값을 무조건 믿지 마세요** — 이
     세션에서 실제로 stale한 값이 몇 번 발견됐습니다(예: my-cv/my-resume). `wrangler.toml`의
     `routes`/커스텀 도메인 설정이나 README를 함께 확인해 실제 배포 주소와 맞는지
     교차검증하세요.
   - 그래도 못 찾겠으면 site_url 없이 등록부터 하고(나중에
     `lens project set-site-url <slug> <url>`로 채울 수 있음), 사용자에게 실제 배포
     URL을 아는지 물어보세요 — site_url이 있어야 GA4 웹 스트림을 만들 수 있습니다.

3. project-lens 레포 루트에서 `lens` 실행 파일을 찾습니다 (PATH에 있으면 `lens`,
   없으면 `<project-lens repo>/.venv/bin/lens`). 다음을 실행하세요:

   ```
   lens project add <GITHUB_URL> --metadata-only \
     [--deployment-type cloudflare_workers|oh_my_homelab|vercel|github_pages] \
     [--site-url <실제 배포 URL>]
   ```

4. 성공하면 등록된 slug/visibility/deployment_type/status를 요약해서 보여주세요.
   실패하면(인증 안 됨, 접근 권한 없음, URL 형식 오류 등) 에러 메시지를 그대로 보여주고,
   `AuthError`면 `gh auth login`을, `RepoAccessError`면 조직 접근 권한 확인을 안내하세요
   (자세한 절차는 `docs/SECURITY.md` 참고).

5. **등록만으로 끝나지 않습니다.** GA4 속성/GTM 컨테이너 생성, 트래킹 스니펫 삽입, PR
   생성까지 전부 자동화돼 있습니다 — 등록이 끝나면 바로 이어서 진행할지 물어보세요:
   "GA4/GTM 트래킹까지 지금 설정할까요?" 사용자가 원하면 `/lens-sync <slug>`로
   이어가세요(먼저 dry-run으로 보여준 뒤 확인받고 `--yes` 실행하는 절차는 그 커맨드가
   담당합니다).

   원하지 않으면 등록만 해두고, 나중에 `/lens-sync <slug>`로 아무 때나 이어갈 수 있다고
   안내하세요.

6. site_url을 모른 채 등록했다면, 나중에 실제 배포 URL을 알게 되면
   `lens project set-site-url <slug> <url>`로 채워야 GA4 스트림을 만들 수 있다는 점을
   언급하세요.
