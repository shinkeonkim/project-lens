"""oh-my-homelab(Kubernetes GitOps) 배포 어댑터 (docs/ADAPTERS.md).

두 단계로 시도한다:

1. `_inject_codekr_style()` — 실제로 조사한 `shinkeonkim/codekr` 레포 구조(Next.js
   App Router + Feature-Sliced Design + 빌드 시점에 굳는 `NEXT_PUBLIC_*`)에 맞춘
   앵커 기반 정밀 패치. GTM ID 자체는 어떤 파일에도 하드코딩하지 않는다 — Next.js는
   `NEXT_PUBLIC_*` 값을 빌드 시점에만 번들에 굳히므로(런타임 K8s 환경변수로는 못
   바꿈), 이 프로젝트는 공개 주소든 내부 주소든 같은 이미지를 쓰기 위해 브라우저
   전용 값을 빌드 이미지에 비워 둔다는 규칙을 이미 갖고 있다(codekr repo Dockerfile
   주석). 그래서 실제 값은 codekr 레포의 GitHub Actions 저장소 변수
   (`vars.NEXT_PUBLIC_GTM_ID`)로 CI 빌드 시점에 주입한다 — `configure_remote()`가
   `--yes`일 때만 그 값을 설정한다(dry-run에서 실제 GitHub 상태를 바꾸지 않기 위함).

2. 앵커가 안 맞으면(예: `kokoa-study-room/aws-study-site`처럼 codekr과 다른
   import/className 스타일을 쓰는 App Router 레포) `_static_site.py`의 범용
   Next.js App Router 폴백으로 넘어간다 — `<head>`/`<body>` JSX만 찾아 그 자리에
   ID를 직접 하드코딩한다. codekr과 달리 여러 이미지가 값을 공유할 필요가 없는
   레포는 CI 변수 배선을 만들 이유가 없어, 다른 정적 사이트 어댑터들과 동일하게
   더 단순한 방식을 쓴다. 그마저도 못 찾으면 None을 반환해 호출자가 이슈 생성
   폴백을 쓰게 한다 — 무리하게 다른 구조를 추측해서 잘못 고치지 않기 위함이다
   (docs/ADAPTERS.md 원칙).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_lens.adapters._static_site import (
    NEXTJS_LAYOUT_CANDIDATES,
    inject_nextjs_app_router_tracking,
)
from project_lens.adapters.base import ChangeSet
from project_lens.errors import DeployError

_LAYOUT_PATH = "apps/web/src/app/layout.tsx"
_DOCKERFILE_PATH = "apps/web/Dockerfile"
_ENV_EXAMPLE_PATH = ".env.example"
_CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
_COMPONENT_PATH = "apps/web/src/shared/analytics/GoogleTagManager.tsx"
_COMPONENT_INDEX_PATH = "apps/web/src/shared/analytics/index.ts"

_COMPONENT_CONTENT = '''/**
 * GTM(Google Tag Manager) 스니펫.
 *
 * `NEXT_PUBLIC_GTM_ID`는 빌드 시점에 박힌다 (apps/web/Dockerfile) — 비어 있으면
 * (로컬 개발, GTM 미설정 배포) 아무것도 렌더링하지 않는다.
 */
const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID;

const HEAD_SCRIPT = `
(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','${GTM_ID}');
`;

export function GoogleTagManagerScript() {
  if (!GTM_ID) return null;
  return <script dangerouslySetInnerHTML={{ __html: HEAD_SCRIPT }} />;
}

export function GoogleTagManagerNoScript() {
  if (!GTM_ID) return null;
  return (
    <noscript>
      <iframe
        src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
        height="0"
        width="0"
        style={{ display: "none", visibility: "hidden" }}
        title="Google Tag Manager"
      />
    </noscript>
  );
}
'''

_COMPONENT_INDEX_CONTENT = (
    'export { GoogleTagManagerNoScript, GoogleTagManagerScript } from "./GoogleTagManager";\n'
)

_LAYOUT_IMPORT_ANCHOR = 'import type { ReactNode } from "react";'
_LAYOUT_IMPORT_LINE = (
    'import { GoogleTagManagerNoScript, GoogleTagManagerScript } from "@/shared/analytics";'
)

_LAYOUT_HEAD_ANCHOR = "        <ThemeScript />"
_LAYOUT_HEAD_LINE = "        <GoogleTagManagerScript />"

_LAYOUT_BODY_ANCHOR = '      <body className="flex min-h-[100dvh] flex-col bg-surface text-ink">'
_LAYOUT_BODY_LINE = "        <GoogleTagManagerNoScript />"

_DOCKERFILE_ARG_ANCHOR = 'ARG NEXT_PUBLIC_WS_BASE_URL=""'
_DOCKERFILE_ARG_LINE = 'ARG NEXT_PUBLIC_GTM_ID=""'

_DOCKERFILE_ENV_ANCHOR = "ENV NEXT_PUBLIC_WS_BASE_URL=$NEXT_PUBLIC_WS_BASE_URL"
_DOCKERFILE_ENV_LINE = "ENV NEXT_PUBLIC_GTM_ID=$NEXT_PUBLIC_GTM_ID"

_ENV_EXAMPLE_ANCHOR = "NEXT_PUBLIC_WS_BASE_URL=ws://localhost:18080"
_ENV_EXAMPLE_LINE = "NEXT_PUBLIC_GTM_ID="

_CI_TAGS_ANCHOR_PREFIX = "          tags: "
_CI_BUILD_ARGS_LINES = (
    "          build-args: |\n"
    "            NEXT_PUBLIC_GTM_ID=${{ matrix.app == 'web' && vars.NEXT_PUBLIC_GTM_ID || '' }}"
)

_REQUIRED_PATHS = (_LAYOUT_PATH, _DOCKERFILE_PATH, _ENV_EXAMPLE_PATH, _CI_WORKFLOW_PATH)


class OhMyHomelabAdapter:
    name = "oh_my_homelab"

    def detect(self, repo_path: Path) -> bool:
        return (repo_path / "deploy" / "charts").is_dir()

    def inject_tracking(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        component_path = repo_path / _COMPONENT_PATH
        if component_path.exists():
            return ChangeSet(
                changed_files=(),
                summary=f"{_COMPONENT_PATH}가 이미 존재합니다 (GTM 배선이 이미 되어 있음).",
                already_present=True,
            )

        has_codekr_shape = all((repo_path / p).exists() for p in _REQUIRED_PATHS)
        if has_codekr_shape:
            # 파일 경로 자체는 codekr과 같다 — anchor 문자열이 드리프트된 것뿐일 수
            # 있으니, 여기서는 범용 폴백으로 새지 않고 보수적으로 None(이슈 생성)을
            # 유지한다. codekr은 이미지 하나를 공개/내부 두 배포가 같이 쓰기 때문에
            # ID를 소스에 직접 박으면(범용 폴백 방식) 그 전제가 깨진다 — CI 변수
            # 배선이 codekr에는 필수다.
            return self._inject_codekr_style(repo_path, gtm_id)

        # 경로 구조 자체가 codekr과 다른 다른 homelab 레포(예: aws-study-site) —
        # App Router 구조 자체는 흔하므로, <head>/<body> JSX만 있으면 그 자리에
        # 직접 값을 꽂는 범용 폴백을 쓴다. (codekr과 달리 여러 이미지가 값을 공유할
        # 필요가 없는 레포는 CI 변수 배선을 만들 이유가 없어, 다른 static 어댑터들과
        # 동일하게 ID를 소스에 직접 하드코딩한다.)
        for candidate in NEXTJS_LAYOUT_CANDIDATES:
            layout_path = repo_path / candidate
            if layout_path.exists():
                return inject_nextjs_app_router_tracking(repo_path, layout_path, gtm_id)

        return None

    def _inject_codekr_style(self, repo_path: Path, gtm_id: str) -> ChangeSet | None:
        component_path = repo_path / _COMPONENT_PATH
        layout_path = repo_path / _LAYOUT_PATH
        dockerfile_path = repo_path / _DOCKERFILE_PATH
        env_example_path = repo_path / _ENV_EXAMPLE_PATH
        ci_workflow_path = repo_path / _CI_WORKFLOW_PATH

        layout = layout_path.read_text(encoding="utf-8")
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
        env_example = env_example_path.read_text(encoding="utf-8")
        ci_workflow = ci_workflow_path.read_text(encoding="utf-8")

        if (
            _LAYOUT_IMPORT_ANCHOR not in layout
            or _LAYOUT_HEAD_ANCHOR not in layout
            or _LAYOUT_BODY_ANCHOR not in layout
            or _DOCKERFILE_ARG_ANCHOR not in dockerfile
            or _DOCKERFILE_ENV_ANCHOR not in dockerfile
            or _ENV_EXAMPLE_ANCHOR not in env_example
            or not any(
                line.startswith(_CI_TAGS_ANCHOR_PREFIX) for line in ci_workflow.splitlines()
            )
        ):
            return None

        layout = layout.replace(
            _LAYOUT_IMPORT_ANCHOR, f"{_LAYOUT_IMPORT_ANCHOR}\n{_LAYOUT_IMPORT_LINE}", 1
        )
        layout = layout.replace(
            _LAYOUT_HEAD_ANCHOR, f"{_LAYOUT_HEAD_ANCHOR}\n{_LAYOUT_HEAD_LINE}", 1
        )
        layout = layout.replace(
            _LAYOUT_BODY_ANCHOR, f"{_LAYOUT_BODY_ANCHOR}\n{_LAYOUT_BODY_LINE}", 1
        )

        dockerfile = dockerfile.replace(
            _DOCKERFILE_ARG_ANCHOR, f"{_DOCKERFILE_ARG_ANCHOR}\n{_DOCKERFILE_ARG_LINE}", 1
        )
        dockerfile = dockerfile.replace(
            _DOCKERFILE_ENV_ANCHOR, f"{_DOCKERFILE_ENV_ANCHOR}\n{_DOCKERFILE_ENV_LINE}", 1
        )

        env_example = env_example.replace(
            _ENV_EXAMPLE_ANCHOR, f"{_ENV_EXAMPLE_ANCHOR}\n{_ENV_EXAMPLE_LINE}", 1
        )

        ci_lines = ci_workflow.splitlines(keepends=True)
        for index, line in enumerate(ci_lines):
            if line.startswith(_CI_TAGS_ANCHOR_PREFIX):
                newline = "\n" if line.endswith("\n") else ""
                ci_lines.insert(index + 1, f"{_CI_BUILD_ARGS_LINES}{newline}")
                break
        ci_workflow = "".join(ci_lines)

        component_path.parent.mkdir(parents=True, exist_ok=True)
        component_path.write_text(_COMPONENT_CONTENT, encoding="utf-8")
        (repo_path / _COMPONENT_INDEX_PATH).write_text(_COMPONENT_INDEX_CONTENT, encoding="utf-8")
        layout_path.write_text(layout, encoding="utf-8")
        dockerfile_path.write_text(dockerfile, encoding="utf-8")
        env_example_path.write_text(env_example, encoding="utf-8")
        ci_workflow_path.write_text(ci_workflow, encoding="utf-8")

        return ChangeSet(
            changed_files=(
                _COMPONENT_PATH,
                _COMPONENT_INDEX_PATH,
                _LAYOUT_PATH,
                _DOCKERFILE_PATH,
                _ENV_EXAMPLE_PATH,
                _CI_WORKFLOW_PATH,
            ),
            summary=(
                "GTM 컴포넌트를 추가하고 layout.tsx/Dockerfile/.env.example/CI 워크플로에 "
                "NEXT_PUBLIC_GTM_ID 배선을 연결했습니다 (값 자체는 CI 저장소 변수로 별도 설정)."
            ),
        )

    def configure_remote(self, *, github_org: str, github_repo: str, gtm_id: str) -> str:
        """codekr CI가 빌드 시점에 읽는 GitHub Actions 저장소 변수를 설정한다.

        --yes일 때만 호출해야 한다 — 실제 GitHub 상태를 바꾸는 유일한 지점이라
        dry-run에서는 절대 호출하면 안 된다.
        """

        result = subprocess.run(
            [
                "gh",
                "variable",
                "set",
                "NEXT_PUBLIC_GTM_ID",
                "--repo",
                f"{github_org}/{github_repo}",
                "--body",
                gtm_id,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise DeployError(
                f"GitHub Actions 저장소 변수 설정 실패(NEXT_PUBLIC_GTM_ID): {result.stderr.strip()}"
            )
        return f"{github_org}/{github_repo}의 NEXT_PUBLIC_GTM_ID 저장소 변수를 {gtm_id}로 설정했습니다."
