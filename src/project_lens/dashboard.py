"""로컬 대시보드 HTML 생성.

project-lens가 클라우드에 아무것도 올리지 않는다는 원칙과 같은 이유로, 이 대시보드도
로컬 정적 HTML 파일이다 — 매번 `lens dashboard`를 실행할 때 레지스트리 + (가능하면)
실시간 GA4 수치를 읽어 파일을 새로 만들고, 사용자가 브라우저로 직접 연다.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

_STATUS_LABELS = {
    "active": ("활성", "ok"),
    "pending": ("대기", "pending"),
    "needs_attention": ("확인 필요", "warn"),
    "archived": ("보관됨", "muted"),
}


@dataclass
class DashboardRow:
    slug: str
    github_url: str
    site_url: str | None
    status: str
    deployment_type: str
    pr_url: str | None
    pr_state: str | None
    run_status: str | None
    run_summary: str | None
    ga4_measurement_id: str | None
    gtm_console_url: str | None
    ga4_active_users_7d: str | None
    ga4_sessions_7d: str | None
    site_health_status: str = "unknown"  # "up" | "down" | "error" | "unknown"
    site_health_detail: str | None = None


DEFAULT_SERVE_PORT = 8765


def render_dashboard_html(
    rows: list[DashboardRow], generated_at: str, *, serve_port: int = DEFAULT_SERVE_PORT
) -> str:
    total = len(rows)
    active = sum(1 for r in rows if r.status == "active")
    needs_attention = sum(1 for r in rows if r.status == "needs_attention")
    merged = sum(1 for r in rows if r.pr_state == "MERGED")
    open_prs = sum(1 for r in rows if r.pr_state == "OPEN")
    sites_down = sum(1 for r in rows if r.site_health_status == "down")

    ga4_rows = [r for r in rows if r.ga4_active_users_7d is not None]
    total_active_users = sum(int(r.ga4_active_users_7d) for r in ga4_rows)
    total_sessions = sum(int(r.ga4_sessions_7d or "0") for r in ga4_rows)

    cards = "\n".join(_render_card(r) for r in sorted(rows, key=lambda r: r.slug))
    ga4_summary_table = _render_ga4_summary_table(ga4_rows)
    ga4_totals_stats = (
        f'<div class="stat"><span class="stat-value">{total_active_users}</span>'
        f'<span class="stat-label">합계 방문자(7일)</span></div>\n'
        f'  <div class="stat"><span class="stat-value">{total_sessions}</span>'
        f'<span class="stat-label">합계 세션(7일)</span></div>'
        if ga4_rows
        else ""
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>project-lens 대시보드</title>
<style>
{_CSS}
</style>
</head>
<body>
<header>
  <div class="header-row">
    <h1>project-lens 대시보드</h1>
    <div class="refresh">
      <button id="refresh-btn" onclick="refreshDashboard()">↻ 새로고침</button>
      <span id="refresh-status" class="muted-text"></span>
    </div>
  </div>
  <p class="generated">생성: {html.escape(generated_at)}</p>
</header>

<script>
const REFRESH_URL = "http://127.0.0.1:{serve_port}/refresh";
async function refreshDashboard() {{
  const btn = document.getElementById("refresh-btn");
  const status = document.getElementById("refresh-status");
  btn.disabled = true;
  status.textContent = "새로고침 중... (GA4/PR 상태를 다시 불러옵니다)";
  try {{
    const res = await fetch(REFRESH_URL, {{ method: "POST" }});
    if (!res.ok) throw new Error(await res.text());
    location.reload();
  }} catch (e) {{
    status.textContent = "실패 — `lens dashboard --serve`로 켜져 있는지 확인하세요.";
    btn.disabled = false;
  }}
}}
</script>

<section class="stats">
  <div class="stat"><span class="stat-value">{total}</span><span class="stat-label">전체 프로젝트</span></div>
  <div class="stat ok"><span class="stat-value">{active}</span><span class="stat-label">활성</span></div>
  <div class="stat warn"><span class="stat-value">{needs_attention}</span><span class="stat-label">확인 필요</span></div>
  <div class="stat"><span class="stat-value">{merged}</span><span class="stat-label">PR 머지됨</span></div>
  <div class="stat"><span class="stat-value">{open_prs}</span><span class="stat-label">PR 대기</span></div>
  <div class="stat {'warn' if sites_down else ''}"><span class="stat-value">{sites_down}</span><span class="stat-label">사이트 응답 없음</span></div>
  {ga4_totals_stats}
</section>

{ga4_summary_table}

<section class="cards">
{cards}
</section>

<footer>
  <p>이 파일은 <code>lens dashboard</code> 실행 시점의 스냅샷입니다. 다시 실행하면
  갱신됩니다. GA4 수치는 최근 7일 기준이며, 인증/속성 정보가 없으면 비어 있습니다.</p>
</footer>
</body>
</html>
"""


def _render_ga4_summary_table(ga4_rows: list[DashboardRow]) -> str:
    """GA4 속성이 프로젝트마다 따로 떨어져 있어 콘솔을 하나씩 열어봐야 하는 문제를 없애기
    위한 표. 트래픽이 많은 순으로 정렬해 어떤 사이트를 먼저 봐야 할지 한눈에 보여준다."""

    if not ga4_rows:
        return ""

    sorted_rows = sorted(ga4_rows, key=lambda r: int(r.ga4_active_users_7d), reverse=True)
    body_rows = "\n".join(
        f'<tr><td><a href="{html.escape(r.github_url)}" target="_blank" rel="noopener">'
        f'{html.escape(r.slug)}</a></td>'
        f'<td class="num">{html.escape(r.ga4_active_users_7d)}</td>'
        f'<td class="num">{html.escape(r.ga4_sessions_7d or "0")}</td>'
        f'<td>{html.escape(r.ga4_measurement_id or "-")}</td></tr>'
        for r in sorted_rows
    )
    return f"""<section class="ga4-summary">
  <h2>GA4 요약 (방문자 많은 순)</h2>
  <table>
    <thead><tr><th>프로젝트</th><th class="num">방문자(7일)</th><th class="num">세션(7일)</th><th>측정 ID</th></tr></thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</section>"""


_HEALTH_LABELS = {
    "up": ("● 정상", "health-up"),
    "down": ("● 응답 없음", "health-down"),
    "unknown": ("", "health-unknown"),
}


def _render_card(r: DashboardRow) -> str:
    label, css_class = _STATUS_LABELS.get(r.status, (r.status, "muted"))
    site_link = (
        f'<a href="{html.escape(r.site_url)}" target="_blank" rel="noopener">{html.escape(r.site_url)}</a>'
        if r.site_url
        else '<span class="muted-text">사이트 URL 없음</span>'
    )
    health_text, health_class = _HEALTH_LABELS.get(r.site_health_status, ("", "health-unknown"))
    health_title = f' title="{html.escape(r.site_health_detail)}"' if r.site_health_detail else ""
    health_badge = (
        f'<span class="health {health_class}"{health_title}>{health_text}</span>' if health_text else ""
    )

    if r.pr_url:
        pr_badge_class = {"MERGED": "ok", "OPEN": "pending", "CLOSED": "muted"}.get(
            r.pr_state or "", "muted"
        )
        pr_label = {"MERGED": "머지됨", "OPEN": "열림", "CLOSED": "닫힘"}.get(
            r.pr_state or "", r.pr_state or "?"
        )
        pr_html = (
            f'<a href="{html.escape(r.pr_url)}" target="_blank" rel="noopener" '
            f'class="badge {pr_badge_class}">PR {html.escape(pr_label)}</a>'
        )
    else:
        pr_html = '<span class="badge muted">PR 없음</span>'

    ga_html = ""
    if r.ga4_active_users_7d is not None:
        ga_html = (
            f'<div class="ga4">방문자(7일) <strong>{html.escape(r.ga4_active_users_7d)}</strong>'
            f" · 세션 <strong>{html.escape(r.ga4_sessions_7d or '0')}</strong></div>"
        )

    links = []
    links.append(f'<a href="{html.escape(r.github_url)}" target="_blank" rel="noopener">GitHub</a>')
    if r.gtm_console_url:
        links.append(f'<a href="{html.escape(r.gtm_console_url)}" target="_blank" rel="noopener">GTM</a>')
    if r.ga4_measurement_id:
        links.append(f'<span class="muted-text">{html.escape(r.ga4_measurement_id)}</span>')

    run_note = ""
    if r.run_summary:
        run_note = f'<div class="run-summary">{html.escape(r.run_summary)}</div>'

    return f"""<article class="card">
  <div class="card-head">
    <h2><a href="{html.escape(r.github_url)}" target="_blank" rel="noopener">{html.escape(r.slug)}</a></h2>
    <span class="badge {css_class}">{html.escape(label)}</span>
  </div>
  <div class="site">{site_link} {health_badge}</div>
  <div class="deployment-type">{html.escape(r.deployment_type)}</div>
  {ga_html}
  <div class="badges">{pr_html}</div>
  {run_note}
  <div class="links">{" · ".join(links)}</div>
</article>"""


_CSS = """
:root {
  color-scheme: light dark;
  --bg: #f7f7f8;
  --fg: #1a1a1a;
  --muted: #6b7280;
  --card-bg: #ffffff;
  --border: #e5e7eb;
  --ok: #15803d;
  --ok-bg: #dcfce7;
  --warn: #b45309;
  --warn-bg: #fef3c7;
  --pending: #1d4ed8;
  --pending-bg: #dbeafe;
  --muted-bg: #f3f4f6;
  --link: #2563eb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f0f10;
    --fg: #e5e7eb;
    --muted: #9ca3af;
    --card-bg: #1a1a1c;
    --border: #2a2a2d;
    --ok-bg: #052e16;
    --ok: #4ade80;
    --warn-bg: #451a03;
    --warn: #fbbf24;
    --pending-bg: #172554;
    --pending: #60a5fa;
    --muted-bg: #27272a;
    --link: #60a5fa;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem;
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  max-width: 1100px;
  margin-inline: auto;
}
.header-row { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
header h1 { margin-bottom: 0.25rem; font-size: 1.5rem; }
.generated { color: var(--muted); font-size: 0.85rem; margin-top: 0; }
.refresh { display: flex; align-items: center; gap: 0.6rem; font-size: 0.8rem; }
#refresh-btn {
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--fg);
  border-radius: 8px;
  padding: 0.4rem 0.8rem;
  font-size: 0.85rem;
  cursor: pointer;
}
#refresh-btn:hover:not(:disabled) { border-color: var(--link); color: var(--link); }
#refresh-btn:disabled { opacity: 0.6; cursor: default; }
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 1.5rem 0;
}
.stat {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem 1.25rem;
  min-width: 110px;
}
.stat-value { display: block; font-size: 1.5rem; font-weight: 700; }
.stat-label { display: block; font-size: 0.8rem; color: var(--muted); }
.stat.ok .stat-value { color: var(--ok); }
.stat.warn .stat-value { color: var(--warn); }
.ga4-summary {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  margin: 1.5rem 0;
  overflow-x: auto;
}
.ga4-summary h2 { font-size: 1rem; margin: 0 0 0.75rem; }
.ga4-summary table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.ga4-summary th, .ga4-summary td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border); }
.ga4-summary th.num, .ga4-summary td.num { text-align: right; }
.ga4-summary tbody tr:last-child td { border-bottom: none; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.9rem;
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.1rem;
}
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.card-head h2 { font-size: 0.95rem; margin: 0; word-break: break-all; }
.card-head h2 a { color: inherit; text-decoration: none; }
.card-head h2 a:hover { text-decoration: underline; }
.site { margin: 0.4rem 0; font-size: 0.85rem; overflow-wrap: anywhere; }
.health { font-size: 0.75rem; font-weight: 600; white-space: nowrap; }
.health-up { color: var(--ok); }
.health-down { color: var(--warn); }
.deployment-type { font-size: 0.75rem; color: var(--muted); margin-bottom: 0.5rem; }
.ga4 { font-size: 0.85rem; margin: 0.4rem 0; }
.badges { margin: 0.5rem 0; }
.badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  text-decoration: none;
  font-weight: 600;
}
.badge.ok { background: var(--ok-bg); color: var(--ok); }
.badge.warn { background: var(--warn-bg); color: var(--warn); }
.badge.pending { background: var(--pending-bg); color: var(--pending); }
.badge.muted { background: var(--muted-bg); color: var(--muted); }
.run-summary { font-size: 0.78rem; color: var(--muted); margin: 0.4rem 0; }
.links { font-size: 0.8rem; margin-top: 0.5rem; }
.links a { color: var(--link); text-decoration: none; }
.links a:hover { text-decoration: underline; }
.muted-text { color: var(--muted); }
footer { margin-top: 2rem; color: var(--muted); font-size: 0.8rem; }
a { color: var(--link); }
"""
