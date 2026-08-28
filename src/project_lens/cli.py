from __future__ import annotations

import json
import uuid
import webbrowser
from datetime import datetime, timezone

import click

from project_lens.adapters.cloudflare_workers import CloudflareWorkersAdapter
from project_lens.adapters.github_pages import GitHubPagesAdapter
from project_lens.adapters.oh_my_homelab import OhMyHomelabAdapter
from project_lens.adapters.vercel import VercelAdapter
from project_lens.config import dashboard_path, reports_dir
from project_lens.dashboard import DashboardRow, render_dashboard_html
from project_lens.errors import AdapterDetectionError, LensError, ValidationError
from project_lens.github.client import ensure_authenticated, pr_state, view_repo
from project_lens.github.repo_ops import (
    commit_all,
    create_branch,
    create_issue,
    create_pull_request,
    push_branch,
)
from project_lens.google import ads, ga4, ga4_reporting, gtm
from project_lens.google.auth import (
    has_ads_developer_token,
    has_stored_credentials,
    load_ads_developer_token,
    load_credentials,
    run_oauth_flow,
    store_ads_developer_token,
)
from project_lens.registry.db import connect
from project_lens.registry.repository import (
    finish_run,
    get_latest_pr_run,
    get_latest_run,
    get_project,
    get_run,
    get_tracking_config,
    list_projects,
    set_project_status,
    set_site_url,
    start_run,
    upsert_project,
    upsert_tracking_config,
)
from project_lens.settings import load_settings, save_settings
from project_lens.workspace.manager import cloned_workspace

_ADAPTERS = [
    CloudflareWorkersAdapter(),
    VercelAdapter(),
    GitHubPagesAdapter(),
    OhMyHomelabAdapter(),
]


@click.group()
def main() -> None:
    """project-lens: 여러 웹사이트의 GA4/GTM/Google Ads 트래킹 설정 관리 CLI."""


@main.group()
def project() -> None:
    """프로젝트 레지스트리 관리."""


@project.command("add")
@click.argument("github_url")
@click.option(
    "--metadata-only",
    is_flag=True,
    required=True,
    help=(
        "레지스트리 등록만 수행합니다. 트래킹 자동 세팅(GA4/GTM 생성, 스니펫 삽입, PR 생성)은 "
        "아직 구현되지 않았습니다 (docs/ROADMAP.md Phase 1+). 현재는 이 플래그가 필수입니다."
    ),
)
@click.option(
    "--deployment-type",
    type=click.Choice(
        ["cloudflare_workers", "oh_my_homelab", "vercel", "github_pages", "unknown"]
    ),
    default="unknown",
    help="배포 방식을 미리 알고 있다면 지정합니다 (자동 감지는 Phase 1부터 지원).",
)
@click.option(
    "--site-url",
    default=None,
    help="실제 배포 URL (예: https://dice-art.example.com). GA4 웹 스트림 자동 생성에 필요합니다.",
)
def project_add(
    github_url: str, metadata_only: bool, deployment_type: str, site_url: str | None
) -> None:
    """GITHUB_URL을 레지스트리에 등록(이미 있으면 갱신)합니다."""

    ensure_authenticated()
    info = view_repo(github_url)

    conn = connect()
    try:
        record = upsert_project(
            conn,
            github_url=info.url,
            github_org=info.org,
            github_repo=info.repo,
            visibility=info.visibility,
            default_branch=info.default_branch,
            deployment_type=deployment_type,
            site_url=site_url,
        )
    finally:
        conn.close()

    click.echo(
        f"등록됨: {record.slug} ({record.visibility}, "
        f"deployment_type={record.deployment_type}, status={record.status})"
    )


@project.command("list")
def project_list() -> None:
    """등록된 전체 프로젝트를 표로 출력합니다."""

    conn = connect()
    try:
        records = list_projects(conn)
    finally:
        conn.close()

    if not records:
        click.echo("등록된 프로젝트가 없습니다. `lens project add <github_url> --metadata-only`로 추가하세요.")
        return

    rows = [
        (r.slug, r.visibility, r.deployment_type, r.status, r.updated_at) for r in records
    ]
    headers = ("slug", "visibility", "deployment_type", "status", "updated_at")
    widths = [
        max(len(str(row[i])) for row in ([headers] + rows)) for i in range(len(headers))
    ]
    for row in [headers, tuple("-" * w for w in widths)] + rows:
        click.echo("  ".join(str(cell).ljust(w) for cell, w in zip(row, widths)))


@project.command("show")
@click.argument("slug")
def project_show(slug: str) -> None:
    """단일 프로젝트의 상세 정보 + 가장 최근 실행 이력을 출력합니다."""

    conn = connect()
    try:
        record = get_project(conn, slug)
        if record is None:
            raise click.ClickException(f"등록되지 않은 프로젝트입니다: {slug}")
        latest_run = get_latest_run(conn, record.id)
        latest_pr_run = get_latest_pr_run(conn, record.id)
    finally:
        conn.close()

    for field in record.__dataclass_fields__:
        click.echo(f"{field}: {getattr(record, field)}")

    click.echo("")
    click.echo("최근 실행:")
    if latest_run is None:
        click.echo("  없음 (아직 lens track sync --yes를 실행한 적 없음)")
        return

    click.echo(f"  run_id: {latest_run.id} ({latest_run.run_type}, {latest_run.status})")
    if latest_run.summary:
        click.echo(f"  요약: {latest_run.summary}")
    if latest_run.status == "failed":
        click.echo(f"  에러: {latest_run.error_code} — {latest_run.error_summary}")
        click.echo(
            f"  자세한 원인/해결법은 docs/TROUBLESHOOTING.md의 '{latest_run.error_code}' "
            f"항목 또는 `lens logs show {latest_run.id}`를 참고하세요."
        )
    # PR은 그 뒤에 report 같은 run이 더 쌓였을 수 있어 최근 run과 별개로 찾는다
    # (run_type 상관없이 pr_url이 있는 가장 최근 run).
    if latest_pr_run and latest_pr_run.pr_url:
        click.echo(f"  PR: {latest_pr_run.pr_url}")


@project.command("set-site-url")
@click.argument("slug")
@click.argument("site_url")
def project_set_site_url(slug: str, site_url: str) -> None:
    """SLUG 프로젝트의 실제 배포 URL을 설정합니다 (GA4 웹 스트림 자동 생성에 필요)."""

    conn = connect()
    try:
        if get_project(conn, slug) is None:
            raise click.ClickException(f"등록되지 않은 프로젝트입니다: {slug}")
        set_site_url(conn, slug, site_url)
    finally:
        conn.close()

    click.echo(f"{slug}의 site_url을 설정했습니다: {site_url}")


_TROUBLESHOOTING_HINTS = {
    "AuthError": "gh/Google 인증이 필요합니다 — `lens creds check`로 상태를 확인하세요.",
    "RepoAccessError": "레포 접근이 안 됩니다 — URL, 조직 접근 권한(`gh auth status`)을 확인하세요.",
    "AdapterDetectionError": (
        "배포 방식을 감지하지 못했습니다 — 등록된 deployment_type이 실제와 맞는지 확인하세요."
    ),
    "GoogleAPIError": (
        "GA4/GTM/Ads API 호출이 실패했습니다 — 계정 권한(`lens creds accounts`)을 확인하세요."
    ),
    "DeployError": "git/gh 작업(브랜치·커밋·PR·이슈·저장소 변수)이 실패했습니다.",
    "ValidationError": "사전 조건이 부족합니다 — 에러 메시지에 적힌 다음 명령을 실행하세요.",
}


@main.group()
def logs() -> None:
    """실행 이력 조회."""


@logs.command("show")
@click.argument("run_id", type=int)
def logs_show(run_id: int) -> None:
    """RUN_ID 실행의 상세 정보와 문제 해결 힌트를 보여줍니다."""

    conn = connect()
    try:
        run = get_run(conn, run_id)
    finally:
        conn.close()

    if run is None:
        raise click.ClickException(f"존재하지 않는 run_id입니다: {run_id}")

    for field in run.__dataclass_fields__:
        click.echo(f"{field}: {getattr(run, field)}")

    if run.status == "failed" and run.error_code:
        hint = _TROUBLESHOOTING_HINTS.get(run.error_code)
        click.echo("")
        click.echo(f"힌트: {hint or '알 수 없는 에러 타입입니다.'}")
        click.echo(f"자세한 절차는 docs/TROUBLESHOOTING.md의 '{run.error_code}' 항목을 참고하세요.")


@main.group()
def creds() -> None:
    """외부 서비스 자격증명 관리 (docs/SECURITY.md)."""


@creds.command("init")
@click.option("--provider", type=click.Choice(["google", "google-ads"]), required=True)
@click.option(
    "--developer-token",
    default=None,
    help="google-ads 전용: Google Ads API Developer Token (도구 및 설정 > API 센터에서 확인).",
)
@click.option(
    "--login-customer-id",
    default=None,
    help="google-ads 전용: MCC(관리자 계정) 아래에서 접근할 때 필요한 로그인 고객 ID.",
)
@click.option(
    "--profile",
    default="default",
    help="google-ads 전용: --login-customer-id를 저장할 계정 프로필 (`lens creds check` 참고).",
)
def creds_init(
    provider: str, developer_token: str | None, login_customer_id: str | None, profile: str
) -> None:
    """PROVIDER 인증을 최초 1회 수행하고 OS 키체인에 저장합니다."""

    if provider == "google":
        run_oauth_flow()
        click.echo("Google 인증 완료. 자격증명은 OS 키체인에 저장되었습니다.")
        return

    if provider == "google-ads":
        if not developer_token:
            raise click.ClickException("google-ads 인증에는 --developer-token이 필요합니다.")
        store_ads_developer_token(developer_token)
        if login_customer_id:
            settings = load_settings()
            settings.get_or_create_profile(profile).ads_login_customer_id = login_customer_id
            save_settings(settings)
        click.echo(
            "Google Ads Developer Token을 저장했습니다. "
            "adwords 스코프가 없는 기존 인증이라면 `lens creds init --provider google`을 "
            "다시 실행해 재인증하세요."
        )


@creds.command("check")
def creds_check() -> None:
    """저장된 자격증명/설정 상태를 보여줍니다."""

    settings = load_settings()
    click.echo(f"google oauth: {'ok' if has_stored_credentials() else 'missing'}")
    click.echo(f"google ads developer token: {'ok' if has_ads_developer_token() else 'missing'}")
    click.echo(f"기본 프로필: {settings.default_profile}")
    click.echo("프로필:")
    for name, profile in settings.profiles.items():
        click.echo(
            f"  [{name}] ga4_account_id={profile.ga4_account_id or '(미설정)'}, "
            f"gtm_account_id={profile.gtm_account_id or '(미설정)'}, "
            f"ads_login_customer_id={profile.ads_login_customer_id or '(미설정)'}"
        )
    if settings.org_profile_map:
        click.echo("org → 프로필 매핑:")
        for org, name in settings.org_profile_map.items():
            click.echo(f"  {org} → {name}")


@creds.command("accounts")
def creds_accounts() -> None:
    """인증된 Google 계정에서 접근 가능한 GA4/GTM 계정 목록을 보여줍니다."""

    credentials = load_credentials()
    click.echo("GA4 계정:")
    for account in ga4.list_accounts(ga4.build_client(credentials)):
        click.echo(f"  {account.id}  {account.display_name}")

    click.echo("GTM 계정:")
    for account in gtm.list_accounts(gtm.build_client(credentials)):
        click.echo(f"  {account.id}  {account.name}")


@creds.command("set-accounts")
@click.option("--ga4-account-id", default=None)
@click.option("--gtm-account-id", default=None)
@click.option(
    "--profile",
    default="default",
    help=(
        "설정을 저장할 계정 프로필 이름. 여러 GA4/GTM 계정을 구분해 쓰고 싶을 때 "
        "(예: 개인용 vs 스터디 랩용) 이름을 새로 지어 만들고, "
        "`lens creds map-org`로 GitHub org에 연결하세요. 생략하면 'default'."
    ),
)
def creds_set_accounts(
    ga4_account_id: str | None, gtm_account_id: str | None, profile: str
) -> None:
    """GTM/GA4 자동 생성 시 사용할 계정 ID를 프로필 단위로 저장합니다 (`lens creds accounts`로 확인)."""

    settings = load_settings()
    account_profile = settings.get_or_create_profile(profile)
    if ga4_account_id:
        account_profile.ga4_account_id = ga4_account_id
    if gtm_account_id:
        account_profile.gtm_account_id = gtm_account_id
    save_settings(settings)
    click.echo(
        f"저장됨 [{profile}]: ga4_account_id={account_profile.ga4_account_id}, "
        f"gtm_account_id={account_profile.gtm_account_id}"
    )


@creds.command("map-org")
@click.argument("github_org")
@click.argument("profile")
def creds_map_org(github_org: str, profile: str) -> None:
    """GITHUB_ORG의 프로젝트가 기본 프로필 대신 PROFILE을 쓰도록 매핑합니다.

    예: kokoa-lab은 랩 계정, shinkeonkim은 개인 계정을 쓰고 싶을 때
    `lens creds set-accounts --profile lab ...` 로 lab 프로필을 만든 뒤
    `lens creds map-org kokoa-lab lab`로 연결합니다.
    """

    settings = load_settings()
    if profile not in settings.profiles:
        raise click.ClickException(
            f"존재하지 않는 프로필입니다: {profile}. "
            f"먼저 `lens creds set-accounts --profile {profile} ...`로 만드세요."
        )
    settings.org_profile_map[github_org] = profile
    save_settings(settings)
    click.echo(f"{github_org} → {profile}로 매핑했습니다.")


@main.group()
def track() -> None:
    """트래킹 스니펫 동기화."""


@track.command("sync")
@click.argument("slug")
@click.option(
    "--gtm-id",
    default=None,
    help=(
        "삽입할 기존 GTM 컨테이너 ID (예: GTM-XXXXXXX). 생략하면 GA4 속성/GTM 컨테이너를 "
        "API로 자동 생성 또는 조회합니다 (사전에 `lens creds init --provider google`, "
        "`lens creds set-accounts`, `lens project set-site-url`이 필요합니다)."
    ),
)
@click.option(
    "--yes",
    is_flag=True,
    help=(
        "실제로 (필요하면 GA4/GTM 리소스 생성 후) 브랜치 생성/커밋/push/PR(또는 이슈) 생성까지 "
        "진행합니다. 생략하면 계획만 보여주고 종료합니다(dry-run)."
    ),
)
@click.option(
    "--keep-workspace",
    is_flag=True,
    help="디버깅용: 작업 후 clone된 디렉터리를 삭제하지 않습니다.",
)
def track_sync(slug: str, gtm_id: str | None, yes: bool, keep_workspace: bool) -> None:
    """SLUG 프로젝트의 레포에 GTM 스니펫을 삽입하고 PR(또는 이슈)을 생성합니다."""

    conn = connect()
    run_id: int | None = None
    try:
        proj = get_project(conn, slug)
        if proj is None:
            raise click.ClickException(
                f"등록되지 않은 프로젝트입니다: {slug} (먼저 `lens project add`로 등록하세요)"
            )

        auto_provision = gtm_id is None

        if auto_provision and not yes:
            click.echo(
                f"[dry-run] {slug}: --gtm-id가 없어 GA4 속성/GTM 컨테이너를 자동 생성 또는 "
                "조회할 예정입니다."
            )
            click.echo(
                "  --yes로 실행하면 실제로 Google API를 호출해 리소스를 만들고, 그 결과로 "
                "얻은 GTM ID로 스니펫 삽입 → PR까지 진행합니다."
            )
            return

        ensure_authenticated()

        if yes:
            run_id = start_run(conn, project_id=proj.id, run_type="sync")
            workspace_token = str(run_id)
        else:
            workspace_token = f"dryrun-{uuid.uuid4().hex[:8]}"

        try:
            if auto_provision:
                gtm_id = _provision_tracking(conn, proj)

            with cloned_workspace(
                proj.slug, workspace_token, proj.github_url, keep=keep_workspace
            ) as repo_path:
                adapter = next((a for a in _ADAPTERS if a.detect(repo_path)), None)
                if adapter is None:
                    raise AdapterDetectionError(
                        f"{slug}의 배포 방식을 자동 감지하지 못했습니다 "
                        f"(현재 지원: {', '.join(a.name for a in _ADAPTERS)})."
                    )

                change_set = adapter.inject_tracking(repo_path, gtm_id)

                if change_set is None:
                    _handle_no_injection_point(conn, proj, gtm_id, repo_path, run_id, yes)
                    return

                if change_set.already_present:
                    _handle_already_present(conn, change_set, run_id, yes)
                    return

                _handle_new_change(conn, proj, gtm_id, change_set, repo_path, run_id, yes, adapter)
        except Exception as exc:
            # LensError뿐 아니라 어떤 예외든(Google 클라이언트 라이브러리가 던지는 원시
            # TypeError/RefreshError 포함) run을 'running'으로 남겨두지 않고 실패로
            # 기록한다 — 실제로 list_properties() 호출 시그니처 오류, OAuth 스코프
            # 부족으로 인한 RefreshError가 LensError가 아니라서 이 처리가 없으면
            # deploy_runs에 영영 끝나지 않는 'running' 행이 남았다.
            if run_id is not None:
                finish_run(
                    conn,
                    run_id,
                    status="failed",
                    error_code=type(exc).__name__,
                    error_summary=str(exc),
                )
            raise
    finally:
        conn.close()


@track.command("link-ads")
@click.argument("slug")
@click.option(
    "--customer-id",
    required=True,
    help="연결할 Google Ads customer ID (하이픈 없이 숫자만, 예: 1112223333).",
)
@click.option(
    "--yes",
    is_flag=True,
    help=(
        "실제로 GA4-Ads 연결을 생성합니다 (Developer Token이 있으면 전환 액션도 함께). "
        "생략하면 계획만 보여주고 종료합니다(dry-run)."
    ),
)
def track_link_ads(slug: str, customer_id: str, yes: bool) -> None:
    """SLUG의 GA4 속성을 Google Ads customer_id와 연결합니다.

    사전에 `lens track sync`로 GA4 속성이 만들어져 있어야 합니다. Developer Token이
    등록돼 있으면(`lens creds init --provider google-ads`) 전환 액션도 함께 생성합니다 —
    없으면 GA4-Ads 연결만 하고 건너뜁니다.
    """

    conn = connect()
    run_id: int | None = None
    try:
        proj = get_project(conn, slug)
        if proj is None:
            raise click.ClickException(f"등록되지 않은 프로젝트입니다: {slug}")

        tracking = get_tracking_config(conn, proj.id)
        if tracking is None or not tracking.ga4_property_id:
            raise click.ClickException(
                f"{slug}에 GA4 속성이 없습니다. 먼저 `lens track sync {slug} --yes`로 "
                "GA4/GTM을 세팅하세요."
            )

        ads_ready = has_ads_developer_token()

        if not yes:
            click.echo(
                f"[dry-run] {slug}: GA4 속성 properties/{tracking.ga4_property_id} ↔ "
                f"Ads customer {customer_id} 연결 예정."
            )
            if ads_ready:
                click.echo("  Developer Token이 있어 전환 액션도 함께 생성합니다.")
            else:
                click.echo(
                    "  Developer Token이 없어 전환 액션 생성은 건너뜁니다 "
                    "(`lens creds init --provider google-ads`로 등록 가능)."
                )
            return

        run_id = start_run(conn, project_id=proj.id, run_type="sync")
        try:
            credentials = load_credentials()
            ga4_client = ga4.build_client(credentials)
            link = ga4.ensure_google_ads_link(
                ga4_client,
                property_name=f"properties/{tracking.ga4_property_id}",
                customer_id=customer_id,
            )

            conversion_action_resource_name = None
            if ads_ready:
                developer_token = load_ads_developer_token()
                account_profile = load_settings().profile_for_org(proj.github_org)
                ads_client = ads.build_client(
                    credentials,
                    developer_token=developer_token,
                    login_customer_id=account_profile.ads_login_customer_id,
                )
                conversion_action = ads.find_or_create_conversion_action(
                    ads_client, customer_id=customer_id, name=f"{proj.slug} conversion"
                )
                conversion_action_resource_name = conversion_action.resource_name

            existing_ids = json.loads(tracking.ads_conversion_action_ids or "[]")
            if (
                conversion_action_resource_name
                and conversion_action_resource_name not in existing_ids
            ):
                existing_ids.append(conversion_action_resource_name)

            upsert_tracking_config(
                conn,
                project_id=proj.id,
                ads_customer_id=customer_id,
                ads_conversion_action_ids=json.dumps(existing_ids),
            )

            summary = f"GA4-Ads 연결 완료 ({link.name})"
            if conversion_action_resource_name:
                summary += f", 전환 액션: {conversion_action_resource_name}"
            finish_run(conn, run_id, status="success", summary=summary)
            click.echo(summary)
        except Exception as exc:
            finish_run(
                conn, run_id, status="failed", error_code=type(exc).__name__, error_summary=str(exc)
            )
            raise
    finally:
        conn.close()


@track.command("report")
@click.argument("slug")
@click.option(
    "--range",
    "date_range",
    type=click.Choice(["7d", "30d"]),
    default="7d",
    help="조회 기간 (기본 7일).",
)
def track_report(slug: str, date_range: str) -> None:
    """SLUG의 GA4(연결돼 있으면 Ads도) 성과 지표를 조회합니다. 읽기 전용이라 --yes가 없습니다."""

    conn = connect()
    run_id: int | None = None
    try:
        proj = get_project(conn, slug)
        if proj is None:
            raise click.ClickException(f"등록되지 않은 프로젝트입니다: {slug}")

        tracking = get_tracking_config(conn, proj.id)
        if tracking is None or not tracking.ga4_property_id:
            raise click.ClickException(
                f"{slug}에 GA4 속성이 없습니다. 먼저 `lens track sync {slug} --yes`로 "
                "GA4/GTM을 세팅하세요."
            )

        run_id = start_run(conn, project_id=proj.id, run_type="report")
        try:
            credentials = load_credentials()
            lines, summary_line = _fetch_project_report_lines(
                credentials, proj, tracking, date_range
            )
            for line in lines:
                click.echo(line)
            finish_run(conn, run_id, status="success", summary=summary_line)
        except Exception as exc:
            finish_run(
                conn, run_id, status="failed", error_code=type(exc).__name__, error_summary=str(exc)
            )
            raise
    finally:
        conn.close()


@track.command("report-all")
@click.option(
    "--range",
    "date_range",
    type=click.Choice(["7d", "30d"]),
    default="7d",
    help="조회 기간 (기본 7일).",
)
def track_report_all(date_range: str) -> None:
    """GA4가 세팅된 모든 프로젝트의 성과를 한 번에 조회합니다.

    읽기 전용입니다. 결과는 화면에 출력하고 ~/.project-lens/reports/에도 저장합니다 —
    launchd 등으로 비대화형 실행할 때도 기록이 남도록 (docs/SCHEDULED_REPORTS.md).
    """

    conn = connect()
    try:
        projects = [p for p in list_projects(conn) if p.status != "archived"]

        credentials = None
        sections: list[str] = []
        error_lines: list[str] = []
        skipped = 0

        for proj in projects:
            tracking = get_tracking_config(conn, proj.id)
            if tracking is None or not tracking.ga4_property_id:
                skipped += 1
                continue

            run_id = start_run(conn, project_id=proj.id, run_type="report")
            try:
                if credentials is None:
                    credentials = load_credentials()
                lines, summary_line = _fetch_project_report_lines(
                    credentials, proj, tracking, date_range
                )
                sections.append("\n".join(lines))
                finish_run(conn, run_id, status="success", summary=summary_line)
            except Exception as exc:
                finish_run(
                    conn,
                    run_id,
                    status="failed",
                    error_code=type(exc).__name__,
                    error_summary=str(exc),
                )
                error_lines.append(f"{proj.slug}: {type(exc).__name__} — {exc}")
    finally:
        conn.close()

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = f"project-lens 리포트 — 최근 {date_range} (생성 시각: {generated_at})"
    body_parts = [header, ""]
    body_parts.append("\n\n".join(sections) if sections else "(GA4가 세팅된 프로젝트가 없습니다)")
    if error_lines:
        body_parts.append("")
        body_parts.append("조회 실패:")
        body_parts.extend(f"  {line}" for line in error_lines)
    if skipped:
        body_parts.append("")
        body_parts.append(f"({skipped}개 프로젝트는 GA4가 아직 없어 건너뜀)")

    report_text = "\n".join(body_parts)
    click.echo(report_text)

    report_path = reports_dir() / f"{datetime.now(timezone.utc).date().isoformat()}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    click.echo("")
    click.echo(f"저장됨: {report_path}")


def _fetch_project_report_lines(
    credentials, proj, tracking, date_range: str
) -> tuple[list[str], str]:
    """GA4(+가능하면 Ads) 요약을 사람이 읽는 줄 목록과 감사용 한 줄 요약으로 반환한다."""

    data_client = ga4_reporting.build_client(credentials)
    start_date = "30daysAgo" if date_range == "30d" else "7daysAgo"
    ga4_summary = ga4_reporting.run_summary_report(
        data_client, property_id=tracking.ga4_property_id, start_date=start_date
    )

    lines = [
        f"{proj.slug} — 최근 {date_range} GA4 리포트",
        f"  방문자(활성 사용자): {ga4_summary.active_users}",
        f"  세션: {ga4_summary.sessions}",
        f"  페이지뷰: {ga4_summary.page_views}",
        f"  이탈률: {float(ga4_summary.bounce_rate) * 100:.1f}%",
        f"  평균 세션 시간: {float(ga4_summary.avg_session_duration_seconds):.0f}초",
    ]

    if tracking.ads_customer_id and has_ads_developer_token():
        developer_token = load_ads_developer_token()
        account_profile = load_settings().profile_for_org(proj.github_org)
        ads_client = ads.build_client(
            credentials,
            developer_token=developer_token,
            login_customer_id=account_profile.ads_login_customer_id,
        )
        ads_summary = ads.run_summary_report(
            ads_client, customer_id=tracking.ads_customer_id, date_range=date_range
        )
        ctr = (
            (ads_summary.clicks / ads_summary.impressions * 100)
            if ads_summary.impressions
            else 0.0
        )
        lines += [
            "  --- Google Ads ---",
            f"  노출수: {ads_summary.impressions}",
            f"  클릭수: {ads_summary.clicks} (CTR {ctr:.2f}%)",
            f"  비용: {ads_summary.cost:.2f}",
            f"  전환수: {ads_summary.conversions:.1f}",
        ]
    elif tracking.ads_customer_id:
        lines.append("  (Ads 연결은 돼 있지만 Developer Token이 없어 Ads 지표는 건너뜁니다)")

    summary_line = (
        f"GA4 리포트 조회 완료 (방문자 {ga4_summary.active_users}, 세션 {ga4_summary.sessions})"
    )
    return lines, summary_line


def _provision_tracking(conn, proj) -> str:
    """GA4 속성/스트림 + GTM 컨테이너/워크스페이스/태그를 찾거나 만들고, GTM ID를 반환한다.

    find-or-create이므로 같은 프로젝트에 대해 여러 번 호출해도 안전하다 (docs/ARCHITECTURE.md).
    """

    account_profile = load_settings().profile_for_org(proj.github_org)
    if not account_profile.ga4_account_id or not account_profile.gtm_account_id:
        raise ValidationError(
            f"{proj.github_org}에 매핑된 프로필의 GA4/GTM 계정이 설정되지 않았습니다. "
            "`lens creds accounts`로 사용 가능한 계정을 확인한 뒤 "
            "`lens creds set-accounts --ga4-account-id ... --gtm-account-id ... "
            f"[--profile <이름>]`를 먼저 실행하세요 (여러 계정을 org별로 나눠 쓰려면 "
            "`lens creds map-org`도 참고하세요)."
        )
    if not proj.site_url:
        raise ValidationError(
            f"{proj.slug}에 site_url이 설정되지 않았습니다. "
            f"`lens project set-site-url {proj.slug} <실제 배포 URL>`을 먼저 실행하세요."
        )

    credentials = load_credentials()
    ga4_client = ga4.build_client(credentials)
    gtm_service = gtm.build_client(credentials)

    ga4_property = ga4.find_or_create_property(
        ga4_client, account_id=account_profile.ga4_account_id, display_name=proj.slug
    )
    ga4_stream = ga4.find_or_create_web_stream(
        ga4_client,
        property_name=ga4_property.name,
        display_name=proj.slug,
        default_uri=proj.site_url,
    )

    gtm_container = gtm.find_or_create_container(
        gtm_service, account_id=account_profile.gtm_account_id, name=proj.slug
    )
    gtm_workspace = gtm.get_default_workspace(
        gtm_service,
        account_id=account_profile.gtm_account_id,
        container_id=gtm_container.container_id,
    )
    gtm.ensure_ga4_config_tag(
        gtm_service,
        account_id=account_profile.gtm_account_id,
        container_id=gtm_container.container_id,
        workspace_id=gtm_workspace.id,
        measurement_id=ga4_stream.measurement_id,
    )
    published_version = gtm.publish_workspace(
        gtm_service,
        account_id=account_profile.gtm_account_id,
        container_id=gtm_container.container_id,
        workspace_id=gtm_workspace.id,
    )

    upsert_tracking_config(
        conn,
        project_id=proj.id,
        ga4_account_id=account_profile.ga4_account_id,
        ga4_property_id=ga4_property.id,
        ga4_measurement_id=ga4_stream.measurement_id,
        ga4_stream_id=ga4_stream.id,
        gtm_account_id=account_profile.gtm_account_id,
        gtm_container_id=gtm_container.container_id,
        gtm_workspace_id=gtm_workspace.id,
        gtm_last_published_version=published_version,
    )

    return gtm_container.public_id


def _handle_no_injection_point(conn, proj, gtm_id: str, repo_path, run_id, yes: bool) -> None:
    if not yes:
        click.echo(
            f"[dry-run] {proj.slug}: GTM 삽입 지점을 자동으로 찾지 못했습니다 "
            "(확인 경로: index.html, public/index.html, src/index.html)."
        )
        click.echo("  --yes로 실행하면 대신 GitHub 이슈를 생성합니다.")
        return

    issue_url = create_issue(
        repo_path,
        title="[project-lens] GTM 스니펫 자동 삽입 실패 - 수동 확인 필요",
        body=(
            f"project-lens가 GTM({gtm_id}) 스니펫을 삽입할 위치를 자동으로 찾지 못했습니다.\n\n"
            "확인한 경로: `index.html`, `public/index.html`, `src/index.html`\n\n"
            "이 레포의 실제 구조에 맞게 수동으로 GTM 스니펫을 삽입해주세요."
        ),
    )
    set_project_status(conn, proj.slug, "needs_attention")
    finish_run(conn, run_id, status="partial", summary=f"삽입 지점 미발견, 이슈 생성: {issue_url}")
    click.echo(f"삽입 지점을 찾지 못해 이슈를 생성했습니다: {issue_url}")


def _handle_already_present(conn, change_set, run_id, yes: bool) -> None:
    if yes and run_id is not None:
        finish_run(conn, run_id, status="success", summary=change_set.summary)
    click.echo(change_set.summary)


def _handle_new_change(conn, proj, gtm_id: str, change_set, repo_path, run_id, yes: bool, adapter) -> None:
    if not yes:
        click.echo(f"[dry-run] {change_set.summary}")
        click.echo(f"  변경 파일: {', '.join(change_set.changed_files)}")
        click.echo("  --yes로 실행하면 브랜치 생성 → 커밋 → PR까지 진행합니다.")
        return

    remote_summary = None
    configure_remote = getattr(adapter, "configure_remote", None)
    if configure_remote is not None:
        remote_summary = configure_remote(
            github_org=proj.github_org,
            github_repo=proj.github_repo,
            gtm_id=gtm_id,
            changed_files=change_set.changed_files,
        )

    branch = f"project-lens/add-gtm-tracking-{run_id}"
    create_branch(repo_path, branch)
    commit_sha = commit_all(
        repo_path,
        f"chore(tracking): add GTM snippet ({gtm_id})\n\nproject-lens automated commit.",
    )
    push_branch(repo_path, branch)
    pr_body = (
        "project-lens가 자동 생성한 PR입니다.\n\n"
        f"- {change_set.summary}\n"
        f"- GTM 컨테이너: {gtm_id}\n"
    )
    if remote_summary:
        pr_body += f"- {remote_summary}\n"
    pr_url = create_pull_request(
        repo_path,
        title=f"chore(tracking): GTM 스니펫 추가 ({gtm_id})",
        body=pr_body,
        base=proj.default_branch,
    )

    set_project_status(conn, proj.slug, "active")
    summary = change_set.summary + (f" {remote_summary}" if remote_summary else "")
    finish_run(
        conn,
        run_id,
        status="success",
        commit_sha=commit_sha,
        pr_url=pr_url,
        summary=summary,
    )
    click.echo(f"완료: {pr_url}")
    if remote_summary:
        click.echo(remote_summary)


@main.command("dashboard")
@click.option("--no-open", is_flag=True, help="생성 후 브라우저로 자동으로 열지 않습니다.")
@click.option(
    "--offline",
    is_flag=True,
    help="Google API를 호출하지 않고 로컬 레지스트리 정보만으로 생성합니다 (빠르지만 GA4 수치는 비어 있음).",
)
def dashboard(no_open: bool, offline: bool) -> None:
    """등록된 모든 프로젝트 상태를 한눈에 보는 로컬 HTML 대시보드를 만듭니다."""

    conn = connect()
    try:
        projects = list_projects(conn)
        rows: list[DashboardRow] = []
        credentials = None

        for proj in projects:
            tracking = get_tracking_config(conn, proj.id)
            latest_run = get_latest_run(conn, proj.id)
            latest_pr_run = get_latest_pr_run(conn, proj.id)

            pr_state_value = None
            if latest_pr_run and latest_pr_run.pr_url:
                pr_state_value = pr_state(latest_pr_run.pr_url)

            gtm_console_url = None
            if tracking and tracking.gtm_account_id and tracking.gtm_container_id:
                gtm_console_url = (
                    "https://tagmanager.google.com/#/container/accounts/"
                    f"{tracking.gtm_account_id}/containers/{tracking.gtm_container_id}/workspaces"
                )

            ga4_active_users = None
            ga4_sessions = None
            if not offline and tracking and tracking.ga4_property_id:
                try:
                    if credentials is None:
                        credentials = load_credentials()
                    data_client = ga4_reporting.build_client(credentials)
                    summary = ga4_reporting.run_summary_report(
                        data_client, property_id=tracking.ga4_property_id, start_date="7daysAgo"
                    )
                    ga4_active_users = summary.active_users
                    ga4_sessions = summary.sessions
                except Exception:
                    pass  # 대시보드 자체는 계속 만든다 — 그 프로젝트의 GA4 수치만 빈 채로 둔다

            rows.append(
                DashboardRow(
                    slug=proj.slug,
                    github_url=proj.github_url,
                    site_url=proj.site_url,
                    status=proj.status,
                    deployment_type=proj.deployment_type,
                    pr_url=latest_pr_run.pr_url if latest_pr_run else None,
                    pr_state=pr_state_value,
                    run_status=latest_run.status if latest_run else None,
                    run_summary=latest_run.summary if latest_run else None,
                    ga4_measurement_id=tracking.ga4_measurement_id if tracking else None,
                    gtm_console_url=gtm_console_url,
                    ga4_active_users_7d=ga4_active_users,
                    ga4_sessions_7d=ga4_sessions,
                )
            )
    finally:
        conn.close()

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    html_content = render_dashboard_html(rows, generated_at)
    path = dashboard_path()
    path.write_text(html_content, encoding="utf-8")
    click.echo(f"생성됨: {path}")

    if not no_open:
        webbrowser.open(f"file://{path}")


def _entrypoint() -> None:
    try:
        main()
    except LensError as exc:
        click.secho(f"오류: {exc}", fg="red", err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    _entrypoint()
