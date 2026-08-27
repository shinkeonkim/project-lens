"""oh-my-homelab(Kubernetes GitOps) 배포 어댑터 (docs/ADAPTERS.md).

Cloudflare Workers 어댑터와 달리 정규 표현식 기반 범용 패턴이 아니라, 실제로 조사한
`shinkeonkim/codekr` 레포 구조(Next.js App Router + Feature-Sliced Design + 빌드
시점에 굳는 `NEXT_PUBLIC_*`)에 맞춘 앵커 기반 패치다. oh-my-homelab으로 배포되는
다른 레포가 이 구조와 다르면(레이아웃 파일 위치 등) 앵커가 안 맞아 자동으로
None을 반환하고, 호출자가 이슈 생성 폴백을 쓰게 된다 — 무리하게 다른 구조를
추측해서 잘못 고치지 않기 위함이다 (docs/ADAPTERS.md 원칙).

GTM ID 자체는 어떤 파일에도 하드코딩하지 않는다 — Next.js는 `NEXT_PUBLIC_*` 값을
빌드 시점에만 번들에 굳히므로(런타임 K8s 환경변수로는 못 바꿈), 이 프로젝트는
공개 주소든 내부 주소든 같은 이미지를 쓰기 위해 브라우저 전용 값을 빌드 이미지에
비워 둔다는 규칙을 이미 갖고 있다(codekr repo Dockerfile 주석). 그래서 실제 값은
codekr 레포의 GitHub Actions 저장소 변수(`vars.NEXT_PUBLIC_GTM_ID`)로 CI 빌드
시점에 주입한다 — `inject_tracking()`은 그 배선(컴포넌트/레이아웃/Dockerfile
ARG·ENV/CI workflow build-args)만 만들고, 실제 값 설정은 `configure_remote()`가
`--yes`일 때만 수행한다(dry-run에서 실제 GitHub 상태를 바꾸지 않기 위함).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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

        for rel_path in _REQUIRED_PATHS:
            if not (repo_path / rel_path).exists():
                return None

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
