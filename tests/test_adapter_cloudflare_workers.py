from __future__ import annotations

import json

from project_lens.adapters.cloudflare_workers import CloudflareWorkersAdapter

SAMPLE_HTML = """<!doctype html>
<html>
<head>
<title>dice-art</title>
</head>
<body>
<div id="app"></div>
</body>
</html>
"""


def test_detect_wrangler_toml(tmp_path):
    (tmp_path / "wrangler.toml").write_text("name = \"dice-art\"\n")
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_wrangler_jsonc(tmp_path):
    (tmp_path / "wrangler.jsonc").write_text("{}\n")
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_wrangler_in_package_json(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"wrangler": "^3.0.0"}})
    )
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_detect_false_when_no_signal(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))
    assert CloudflareWorkersAdapter().detect(tmp_path) is False


def test_detect_false_on_missing_files(tmp_path):
    assert CloudflareWorkersAdapter().detect(tmp_path) is False


def _mark_wrangler_project(repo_path):
    (repo_path / "wrangler.toml").write_text('name = "dice-art"\n')


def test_inject_tracking_inserts_snippets(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.already_present is False
    assert change_set.changed_files == ("index.html",)

    updated = (tmp_path / "index.html").read_text()
    assert updated.count("GTM-ABC1234") == 2  # head 스니펫 + noscript 스니펫
    assert "googletagmanager.com/gtm.js" in updated
    assert "googletagmanager.com/ns.html" in updated
    # head 스니펫이 <head> 태그 바로 뒤에, noscript 스니펫이 <body> 태그 바로 뒤에 위치해야 함
    assert updated.index("<head>") < updated.index("gtm.js") < updated.index("<body>")
    assert updated.index("<body>") < updated.index("ns.html")


def test_inject_tracking_is_idempotent(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    adapter = CloudflareWorkersAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_inject_tracking_prefers_root_index_html(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set.changed_files == ("index.html",)
    assert "GTM-ABC1234" not in (tmp_path / "public" / "index.html").read_text()


def test_inject_tracking_falls_back_to_public_index_html(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set.changed_files == ("public/index.html",)


def test_inject_tracking_returns_none_when_not_a_wrangler_project(tmp_path):
    (tmp_path / "index.html").write_text(SAMPLE_HTML)
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_inject_tracking_returns_none_when_no_html_entry(tmp_path):
    _mark_wrangler_project(tmp_path)
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


def test_inject_tracking_returns_none_when_html_missing_head_or_body(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "index.html").write_text("<div>no head or body tags</div>")
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


SVELTEKIT_APP_HTML = """<!doctype html>
<html lang="%paraglide.lang%">
	<head>
		<meta charset="utf-8" />
		<link rel="icon" href="%sveltekit.assets%/favicon.svg" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
"""


def test_inject_tracking_finds_sveltekit_src_app_html(tmp_path):
    """실제로 base64-code/qr-gen(SvelteKit)이 이 구조라 삽입 지점을 못 찾고 이슈만 남겼던 회귀 테스트."""

    _mark_wrangler_project(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.html").write_text(SVELTEKIT_APP_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("src/app.html",)
    assert "GTM-ABC1234" in (tmp_path / "src" / "app.html").read_text()


def test_inject_tracking_falls_back_to_any_html_with_head_and_body(tmp_path):
    """알려진 후보 경로 어디에도 없는 구조 — 범용 폴백이 head/body 있는 html을 찾아야 함."""

    _mark_wrangler_project(tmp_path)
    (tmp_path / "custom_entry").mkdir()
    (tmp_path / "custom_entry" / "root.html").write_text(SAMPLE_HTML)
    (tmp_path / "node_modules" / "some_pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "some_pkg" / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("custom_entry/root.html",)


NEXTJS_APP_ROUTER_LAYOUT = """import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
      </head>
      <body>{children}</body>
    </html>
  );
}
"""


def test_inject_tracking_finds_nextjs_app_router_layout(tmp_path):
    """Next.js App Router는 Cloudflare Workers/Vercel/GitHub Pages 어디든 배포될 수

    있으니, 이 공용 전략이 특정 어댑터가 아니라 inject_static_site_tracking()
    디스패치 자체에 걸려 있다는 것도 함께 확인한다."""

    _mark_wrangler_project(tmp_path)
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "layout.tsx").write_text(NEXTJS_APP_ROUTER_LAYOUT)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("src/app/layout.tsx",)

    layout = (tmp_path / "src" / "app" / "layout.tsx").read_text()
    assert "GTM-ABC1234" in layout
    assert "dangerouslySetInnerHTML" in layout
    assert layout.index("<head>") < layout.index("dangerouslySetInnerHTML") < layout.index(
        "<body>"
    )


def test_inject_tracking_nextjs_app_router_is_idempotent(tmp_path):
    _mark_wrangler_project(tmp_path)
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "layout.tsx").write_text(NEXTJS_APP_ROUTER_LAYOUT)
    adapter = CloudflareWorkersAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_detect_true_for_nested_wrangler_project(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "wrangler.jsonc").write_text("{}\n")
    assert CloudflareWorkersAdapter().detect(tmp_path) is True


def test_inject_tracking_finds_html_in_nested_wrangler_project(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "wrangler.jsonc").write_text("{}\n")
    (site / "index.html").write_text(SAMPLE_HTML)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.changed_files == ("site/index.html",)
    assert "GTM-ABC1234" in (site / "index.html").read_text()


DOCUSAURUS_CONFIG = """import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Compiler Study',
  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
        },
        blog: {
          path: 'blog',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    image: 'img/social-card.jpg',
  },
};

export default config;
"""


def _write_docusaurus_project(repo_path):
    site = repo_path / "site"
    site.mkdir()
    (site / "wrangler.jsonc").write_text("{}\n")
    (site / "docusaurus.config.ts").write_text(DOCUSAURUS_CONFIG, encoding="utf-8")
    return site


def test_inject_tracking_adds_docusaurus_google_tag_manager(tmp_path):
    site = _write_docusaurus_project(tmp_path)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.already_present is False
    assert change_set.changed_files == ("site/docusaurus.config.ts",)

    updated = (site / "docusaurus.config.ts").read_text()
    assert 'googleTagManager: {' in updated
    assert 'containerId: "GTM-ABC1234",' in updated
    # googleTagManager가 docs: 보다 앞, 같은 들여쓰기 수준에 있어야 함
    assert updated.index("googleTagManager:") < updated.index("docs:")
    gtm_line = next(l for l in updated.splitlines() if "googleTagManager:" in l)
    docs_line = next(l for l in updated.splitlines() if l.strip().startswith("docs:"))
    assert len(gtm_line) - len(gtm_line.lstrip()) == len(docs_line) - len(docs_line.lstrip())

    # 정적 HTML 경로는 타지 않아야 함 — Docusaurus 소스에는 index.html이 없다.
    assert not (site / "index.html").exists()


def test_inject_tracking_docusaurus_is_idempotent(tmp_path):
    site = _write_docusaurus_project(tmp_path)
    adapter = CloudflareWorkersAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_inject_tracking_docusaurus_returns_none_when_preset_shape_unrecognized(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "wrangler.jsonc").write_text("{}\n")
    (site / "docusaurus.config.ts").write_text(
        "const config = { presets: [] };\nexport default config;\n", encoding="utf-8"
    )

    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None


ASTRO_STARLIGHT_CONFIG = """import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://terraform-study.example.com',
  integrations: [
    starlight({
      title: 'Terraform Study',
      social: [],
    }),
  ],
});
"""


def _write_starlight_project(repo_path):
    repo_path.mkdir(exist_ok=True)
    (repo_path / "wrangler.json").write_text("{}\n")
    (repo_path / "astro.config.mjs").write_text(ASTRO_STARLIGHT_CONFIG, encoding="utf-8")
    return repo_path


def test_inject_tracking_adds_starlight_head_script(tmp_path):
    _write_starlight_project(tmp_path)

    change_set = CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234")

    assert change_set is not None
    assert change_set.already_present is False
    assert change_set.changed_files == ("astro.config.mjs",)

    updated = (tmp_path / "astro.config.mjs").read_text()
    assert "head: [" in updated
    assert "tag: 'script'" in updated
    assert "GTM-ABC1234" in updated
    assert "googletagmanager.com/gtm.js" in updated
    assert updated.index("head: [") < updated.index("title:")


def test_inject_tracking_starlight_is_idempotent(tmp_path):
    _write_starlight_project(tmp_path)
    adapter = CloudflareWorkersAdapter()

    first = adapter.inject_tracking(tmp_path, "GTM-ABC1234")
    second = adapter.inject_tracking(tmp_path, "GTM-ABC1234")

    assert first.already_present is False
    assert second.already_present is True
    assert second.changed_files == ()


def test_inject_tracking_ignores_astro_config_without_starlight(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "wrangler.json").write_text("{}\n")
    (tmp_path / "astro.config.mjs").write_text(
        "export default { integrations: [] };\n", encoding="utf-8"
    )

    # starlight(가 없으니 Astro 설정 삽입 전략을 타지 않고, HTML 폴백도 없으니 None.
    assert CloudflareWorkersAdapter().inject_tracking(tmp_path, "GTM-ABC1234") is None
