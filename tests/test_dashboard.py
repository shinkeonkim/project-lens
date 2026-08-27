from __future__ import annotations

from project_lens.dashboard import DashboardRow, render_dashboard_html


def _row(**overrides):
    defaults = dict(
        slug="kokoa-lab-dice-art",
        github_url="https://github.com/kokoa-lab/dice-art",
        site_url="https://dice-art.example.com",
        status="active",
        deployment_type="cloudflare_workers",
        pr_url="https://github.com/kokoa-lab/dice-art/pull/1",
        pr_state="OPEN",
        run_status="success",
        run_summary="index.html에 GTM(GTM-TEST) 스니펫을 삽입했습니다.",
        ga4_measurement_id="G-ABC123",
        gtm_console_url="https://tagmanager.google.com/#/container/accounts/1/containers/2/workspaces",
        ga4_active_users_7d="42",
        ga4_sessions_7d="50",
    )
    defaults.update(overrides)
    return DashboardRow(**defaults)


def test_render_includes_project_slug_and_links():
    html = render_dashboard_html([_row()], generated_at="2026-08-28T00:00:00+00:00")

    assert "kokoa-lab-dice-art" in html
    assert "https://dice-art.example.com" in html
    assert "https://github.com/kokoa-lab/dice-art/pull/1" in html
    assert "PR 열림" in html
    assert "GTM" in html
    assert "G-ABC123" in html
    assert "방문자(7일)" in html
    assert "42" in html


def test_render_summary_stats_counts():
    rows = [
        _row(slug="a", status="active", pr_state="MERGED"),
        _row(slug="b", status="needs_attention", pr_state="OPEN"),
        _row(slug="c", status="active", pr_state=None, pr_url=None),
    ]
    html = render_dashboard_html(rows, generated_at="2026-08-28T00:00:00+00:00")

    assert "<span class=\"stat-value\">3</span>" in html  # 전체
    assert html.count('class="card"') == 3


def test_render_handles_missing_optional_fields_gracefully():
    row = _row(
        site_url=None,
        pr_url=None,
        pr_state=None,
        run_summary=None,
        ga4_measurement_id=None,
        gtm_console_url=None,
        ga4_active_users_7d=None,
        ga4_sessions_7d=None,
    )
    html = render_dashboard_html([row], generated_at="2026-08-28T00:00:00+00:00")

    assert "사이트 URL 없음" in html
    assert "PR 없음" in html
    # GA4 수치가 없으면 '방문자(7일)' 블록 자체를 안 그린다
    assert "방문자(7일)" not in html


def test_render_escapes_html_in_summary():
    row = _row(run_summary="<script>alert(1)</script>")
    html = render_dashboard_html([row], generated_at="2026-08-28T00:00:00+00:00")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_empty_rows_does_not_crash():
    html = render_dashboard_html([], generated_at="2026-08-28T00:00:00+00:00")
    assert "<span class=\"stat-value\">0</span>" in html


def test_render_ga4_summary_table_sorted_by_active_users_desc():
    rows = [
        _row(slug="low-traffic", ga4_active_users_7d="1", ga4_sessions_7d="1"),
        _row(slug="high-traffic", ga4_active_users_7d="50", ga4_sessions_7d="60"),
    ]
    html = render_dashboard_html(rows, generated_at="2026-08-28T00:00:00+00:00")

    assert "GA4 요약" in html
    assert html.index("high-traffic") < html.index("low-traffic")
    assert "<span class=\"stat-value\">51</span>" in html  # 합계 방문자(7일) = 1 + 50


def test_render_ga4_summary_table_omitted_when_no_ga4_data():
    row = _row(ga4_active_users_7d=None, ga4_sessions_7d=None)
    html = render_dashboard_html([row], generated_at="2026-08-28T00:00:00+00:00")

    assert "GA4 요약" not in html
