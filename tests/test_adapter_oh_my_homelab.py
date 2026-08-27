from __future__ import annotations

import subprocess

import pytest

from project_lens.adapters.oh_my_homelab import OhMyHomelabAdapter
from project_lens.errors import DeployError

LAYOUT_TSX = """import { AuthProvider } from "@/features/auth";
import { SITE_DESCRIPTION, SITE_NAME, SITE_ORIGIN } from "@/shared/config/site";
import { ThemeScript } from "@/shared/theme";
import { ToastViewport } from "@/shared/ui";
import { AppShell } from "@/widgets/app-shell";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body className="flex min-h-[100dvh] flex-col bg-surface text-ink">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
        <ToastViewport />
      </body>
    </html>
  );
}
"""

DOCKERFILE = """FROM oven/bun:1.3-alpine AS builder
ARG NEXT_PUBLIC_API_BASE_URL=""
ARG NEXT_PUBLIC_WS_BASE_URL=""
ARG API_INTERNAL_BASE_URL="http://api:8080"
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_WS_BASE_URL=$NEXT_PUBLIC_WS_BASE_URL
ENV API_INTERNAL_BASE_URL=$API_INTERNAL_BASE_URL
RUN bun run build
"""

ENV_EXAMPLE = """NEXT_PUBLIC_API_BASE_URL=http://localhost:18080
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:18080
"""

CI_WORKFLOW = """jobs:
  images:
    steps:
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/${{ matrix.app }}/Dockerfile
          push: ${{ github.event_name == 'push' }}
          tags: ghcr.io/example/codekr-${{ matrix.app }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
"""


def _write_codekr_fixture(repo_path):
    (repo_path / "deploy" / "charts" / "codekr").mkdir(parents=True)
    (repo_path / "apps" / "web" / "src" / "app").mkdir(parents=True)
    (repo_path / "apps" / "web" / "src" / "app" / "layout.tsx").write_text(
        LAYOUT_TSX, encoding="utf-8"
    )
    (repo_path / "apps" / "web" / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
    (repo_path / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / ".github" / "workflows" / "ci.yml").write_text(CI_WORKFLOW, encoding="utf-8")


def test_detect_true_when_deploy_charts_dir_exists(tmp_path):
    (tmp_path / "deploy" / "charts").mkdir(parents=True)
    assert OhMyHomelabAdapter().detect(tmp_path) is True


def test_detect_false_without_deploy_charts_dir(tmp_path):
    assert OhMyHomelabAdapter().detect(tmp_path) is False


def test_inject_tracking_patches_all_expected_files(tmp_path):
    _write_codekr_fixture(tmp_path)

    change_set = OhMyHomelabAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.already_present is False
    assert set(change_set.changed_files) == {
        "apps/web/src/shared/analytics/GoogleTagManager.tsx",
        "apps/web/src/shared/analytics/index.ts",
        "apps/web/src/app/layout.tsx",
        "apps/web/Dockerfile",
        ".env.example",
        ".github/workflows/ci.yml",
    }

    component = (tmp_path / "apps/web/src/shared/analytics/GoogleTagManager.tsx").read_text()
    assert "NEXT_PUBLIC_GTM_ID" in component
    assert "GoogleTagManagerScript" in component
    assert "GoogleTagManagerNoScript" in component

    index = (tmp_path / "apps/web/src/shared/analytics/index.ts").read_text()
    assert "GoogleTagManagerScript" in index and "GoogleTagManagerNoScript" in index

    layout = (tmp_path / "apps/web/src/app/layout.tsx").read_text()
    assert '@/shared/analytics"' in layout
    assert "<GoogleTagManagerScript />" in layout
    assert "<GoogleTagManagerNoScript />" in layout
    # head 스크립트가 ThemeScript 뒤, body noscript가 body 여는 태그 바로 뒤에 와야 함
    assert layout.index("<ThemeScript />") < layout.index("<GoogleTagManagerScript />")
    assert layout.index('flex-col bg-surface text-ink">') < layout.index(
        "<GoogleTagManagerNoScript />"
    ) < layout.index("<AuthProvider>")

    dockerfile = (tmp_path / "apps/web/Dockerfile").read_text()
    assert 'ARG NEXT_PUBLIC_GTM_ID=""' in dockerfile
    assert "ENV NEXT_PUBLIC_GTM_ID=$NEXT_PUBLIC_GTM_ID" in dockerfile

    env_example = (tmp_path / ".env.example").read_text()
    assert "NEXT_PUBLIC_GTM_ID=" in env_example

    ci_workflow = (tmp_path / ".github/workflows/ci.yml").read_text()
    assert "build-args: |" in ci_workflow
    assert "NEXT_PUBLIC_GTM_ID=" in ci_workflow
    assert "matrix.app == 'web'" in ci_workflow


def test_inject_tracking_is_idempotent(tmp_path):
    _write_codekr_fixture(tmp_path)
    adapter = OhMyHomelabAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_inject_tracking_returns_none_when_layout_missing(tmp_path):
    (tmp_path / "deploy" / "charts" / "codekr").mkdir(parents=True)
    assert OhMyHomelabAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_inject_tracking_returns_none_when_anchor_does_not_match(tmp_path):
    _write_codekr_fixture(tmp_path)
    layout_path = tmp_path / "apps/web/src/app/layout.tsx"
    layout_path.write_text(LAYOUT_TSX.replace("<ThemeScript />", "<SomeOtherScript />"), encoding="utf-8")

    assert OhMyHomelabAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_configure_remote_success(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = OhMyHomelabAdapter().configure_remote(
        github_org="shinkeonkim", github_repo="codekr", gtm_id="GTM-ABC1234"
    )

    assert "NEXT_PUBLIC_GTM_ID" in summary
    assert "GTM-ABC1234" in summary
    assert calls == [
        [
            "gh",
            "variable",
            "set",
            "NEXT_PUBLIC_GTM_ID",
            "--repo",
            "shinkeonkim/codekr",
            "--body",
            "GTM-ABC1234",
        ]
    ]


def test_configure_remote_failure_raises_deploy_error(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="no access")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(DeployError):
        OhMyHomelabAdapter().configure_remote(
            github_org="shinkeonkim", github_repo="codekr", gtm_id="GTM-ABC1234"
        )
