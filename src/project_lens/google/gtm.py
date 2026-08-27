"""Tag Manager API v2 래퍼 (docs/ARCHITECTURE.md의 Google Marketing Service).

Phase 2 범위: GA4 Configuration 태그 + 모든 페이지에서 발동하는 pageview 트리거만 생성한다.
클릭/폼 제출/스크롤 이벤트 태그는 이후 Phase에서 추가한다 (docs/ROADMAP.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from project_lens.errors import GoogleAPIError, short

# GTM 콘솔에서 'GA4 구성' 태그를 만들 때 내부적으로 쓰는 태그 템플릿 ID.
# 공식 REST 문서에는 명시되어 있지 않고, GTM 내보내기(export)와 Terraform
# google_tag_manager_tag 리소스 예제를 통해 확인되는 값이다.
_GA4_CONFIG_TAG_TYPE = "gaawc"

_ALL_PAGES_TRIGGER_NAME = "All Pages (project-lens)"
_GA4_CONFIG_TAG_NAME = "GA4 Configuration (project-lens)"


@dataclass(frozen=True)
class GtmAccount:
    id: str
    name: str


@dataclass(frozen=True)
class GtmContainer:
    account_id: str
    container_id: str
    public_id: str  # "GTM-XXXXXXX"


@dataclass(frozen=True)
class GtmWorkspace:
    id: str


def build_client(credentials: Credentials) -> Resource:
    return build("tagmanager", "v2", credentials=credentials, static_discovery=True)


def list_accounts(service: Resource) -> list[GtmAccount]:
    try:
        response = service.accounts().list().execute()
        return [GtmAccount(id=a["accountId"], name=a["name"]) for a in response.get("account", [])]
    except HttpError as exc:
        raise GoogleAPIError(f"GTM 계정 목록 조회 실패: {short(exc)}") from exc


def find_or_create_container(service: Resource, *, account_id: str, name: str) -> GtmContainer:
    parent = f"accounts/{account_id}"
    try:
        response = service.accounts().containers().list(parent=parent).execute()
        for container in response.get("container", []):
            if container["name"] == name:
                return GtmContainer(
                    account_id=account_id,
                    container_id=container["containerId"],
                    public_id=container["publicId"],
                )

        created = (
            service.accounts()
            .containers()
            .create(parent=parent, body={"name": name, "usageContext": ["web"]})
            .execute()
        )
        return GtmContainer(
            account_id=account_id,
            container_id=created["containerId"],
            public_id=created["publicId"],
        )
    except HttpError as exc:
        raise GoogleAPIError(f"GTM 컨테이너 생성/조회 실패({name}): {short(exc)}") from exc


def get_default_workspace(service: Resource, *, account_id: str, container_id: str) -> GtmWorkspace:
    """새 컨테이너에는 GTM이 'Default Workspace'를 자동으로 만들어준다 — 그걸 그대로 쓴다."""

    parent = f"accounts/{account_id}/containers/{container_id}"
    try:
        response = service.accounts().containers().workspaces().list(parent=parent).execute()
        workspaces = response.get("workspace", [])
        if not workspaces:
            raise GoogleAPIError(f"{parent}에 워크스페이스가 없습니다 (예상치 못한 상태).")
        return GtmWorkspace(id=workspaces[0]["workspaceId"])
    except HttpError as exc:
        raise GoogleAPIError(f"GTM 워크스페이스 조회 실패: {short(exc)}") from exc


def ensure_ga4_config_tag(
    service: Resource,
    *,
    account_id: str,
    container_id: str,
    workspace_id: str,
    measurement_id: str,
) -> str:
    """GA4 Configuration 태그 + 'All Pages' 트리거를 찾거나 만들고, 태그 ID를 반환한다."""

    parent = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
    try:
        trigger_id = _find_or_create_all_pages_trigger(service, parent)

        tags_api = service.accounts().containers().workspaces().tags()
        response = tags_api.list(parent=parent).execute()
        for tag in response.get("tag", []):
            if tag["name"] == _GA4_CONFIG_TAG_NAME:
                return tag["tagId"]

        created = tags_api.create(
            parent=parent,
            body={
                "name": _GA4_CONFIG_TAG_NAME,
                "type": _GA4_CONFIG_TAG_TYPE,
                "parameter": [{"type": "template", "key": "measurementId", "value": measurement_id}],
                "firingTriggerId": [trigger_id],
            },
        ).execute()
        return created["tagId"]
    except HttpError as exc:
        raise GoogleAPIError(f"GA4 Configuration 태그 생성/조회 실패: {short(exc)}") from exc


def _find_or_create_all_pages_trigger(service: Resource, parent: str) -> str:
    triggers_api = service.accounts().containers().workspaces().triggers()
    response = triggers_api.list(parent=parent).execute()
    for trigger in response.get("trigger", []):
        if trigger["name"] == _ALL_PAGES_TRIGGER_NAME:
            return trigger["triggerId"]

    created = triggers_api.create(
        parent=parent, body={"name": _ALL_PAGES_TRIGGER_NAME, "type": "pageview"}
    ).execute()
    return created["triggerId"]


def publish_workspace(service: Resource, *, account_id: str, container_id: str, workspace_id: str) -> str:
    """현재 워크스페이스 상태로 새 버전을 만들고 즉시 게시한다. 게시된 버전 ID를 반환한다."""

    path = f"accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"
    try:
        result = (
            service.accounts()
            .containers()
            .workspaces()
            .create_version(path=path, body={"name": "project-lens automated publish"})
            .execute()
        )
        version = result["containerVersion"]
        service.accounts().containers().versions().publish(path=version["path"]).execute()
        return version["containerVersionId"]
    except HttpError as exc:
        raise GoogleAPIError(f"GTM 워크스페이스 게시 실패: {short(exc)}") from exc
