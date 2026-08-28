from __future__ import annotations

import project_lens.google.gtm as gtm


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeTriggers:
    def __init__(self, state):
        self.state = state

    def list(self, parent):
        return _Exec({"trigger": self.state["triggers"].get(parent, [])})

    def create(self, parent, body):
        trigger = {**body, "triggerId": self.state.next_id()}
        self.state["triggers"].setdefault(parent, []).append(trigger)
        return _Exec(trigger)


class _FakeTags:
    def __init__(self, state):
        self.state = state

    def list(self, parent):
        return _Exec({"tag": self.state["tags"].get(parent, [])})

    def create(self, parent, body):
        tag = {**body, "tagId": self.state.next_id()}
        self.state["tags"].setdefault(parent, []).append(tag)
        return _Exec(tag)


class _FakeVersions:
    def __init__(self, state):
        self.state = state

    def publish(self, path):
        return _Exec({"containerVersion": self.state["versions"][path]})


class _FakeWorkspaces:
    def __init__(self, state):
        self.state = state

    def list(self, parent):
        account_id, container_id = _parse_container_parent(parent)
        return _Exec({"workspace": self.state["workspaces"].get((account_id, container_id), [])})

    def create_version(self, path, body):
        version_id = self.state.next_id()
        version = {"path": path.replace("/workspaces/", "/versions/"), "containerVersionId": version_id}
        self.state["versions"][version["path"]] = version
        return _Exec({"containerVersion": version, "syncStatus": {}})

    def tags(self):
        return _FakeTags(self.state)

    def triggers(self):
        return _FakeTriggers(self.state)


class _FakeContainers:
    def __init__(self, state):
        self.state = state

    def list(self, parent):
        account_id = parent.removeprefix("accounts/")
        return _Exec({"container": self.state["containers"].get(account_id, [])})

    def create(self, parent, body):
        account_id = parent.removeprefix("accounts/")
        container_id = self.state.next_id()
        container = {
            "accountId": account_id,
            "containerId": container_id,
            "name": body["name"],
            "publicId": f"GTM-{container_id}",
            "usageContext": body["usageContext"],
        }
        self.state["containers"].setdefault(account_id, []).append(container)
        # 실제 GTM처럼 컨테이너 생성 시 Default Workspace를 자동으로 만들어준다.
        self.state["workspaces"][(account_id, container_id)] = [
            {"workspaceId": "1", "name": "Default Workspace"}
        ]
        return _Exec(container)

    def workspaces(self):
        return _FakeWorkspaces(self.state)

    def versions(self):
        return _FakeVersions(self.state)


class _FakeAccounts:
    def __init__(self, state):
        self.state = state

    def list(self):
        return _Exec({"account": [{"accountId": "222", "name": "kokoa-lab"}]})

    def containers(self):
        return _FakeContainers(self.state)


class _State(dict):
    def __init__(self):
        super().__init__(containers={}, workspaces={}, triggers={}, tags={}, versions={})
        self._next_id = 0

    def next_id(self) -> str:
        self._next_id += 1
        return str(self._next_id)


class FakeGtmService:
    """googleapiclient의 accounts().containers().workspaces()... 체이닝을 흉내내는 대역."""

    def __init__(self):
        self.state = _State()

    def accounts(self):
        return _FakeAccounts(self.state)


def _parse_container_parent(parent: str) -> tuple[str, str]:
    parts = parent.split("/")
    return parts[1], parts[3]


def test_list_accounts():
    service = FakeGtmService()
    assert gtm.list_accounts(service) == [gtm.GtmAccount(id="222", name="kokoa-lab")]


def test_find_or_create_container_creates_when_missing():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="kokoa-lab-dice-art")

    assert container.account_id == "222"
    assert container.public_id.startswith("GTM-")


def test_find_or_create_container_is_idempotent():
    service = FakeGtmService()
    first = gtm.find_or_create_container(service, account_id="222", name="kokoa-lab-dice-art")
    second = gtm.find_or_create_container(service, account_id="222", name="kokoa-lab-dice-art")

    assert first == second
    assert len(service.state["containers"]["222"]) == 1


def test_get_default_workspace_returns_auto_created_workspace():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")

    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    assert workspace.id == "1"


def test_ensure_ga4_config_tag_creates_trigger_and_tag():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    tag_id = gtm.ensure_ga4_config_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        measurement_id="G-ABC123",
    )

    parent = f"accounts/222/containers/{container.container_id}/workspaces/{workspace.id}"
    assert service.state["triggers"][parent][0]["type"] == "pageview"
    created_tag = service.state["tags"][parent][0]
    assert created_tag["tagId"] == tag_id
    assert created_tag["type"] == "gaawc"
    assert created_tag["parameter"] == [
        {"type": "template", "key": "measurementId", "value": "G-ABC123"}
    ]
    assert created_tag["firingTriggerId"] == [service.state["triggers"][parent][0]["triggerId"]]


def test_ensure_ga4_config_tag_is_idempotent():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    first = gtm.ensure_ga4_config_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        measurement_id="G-ABC123",
    )
    second = gtm.ensure_ga4_config_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        measurement_id="G-ABC123",
    )

    parent = f"accounts/222/containers/{container.container_id}/workspaces/{workspace.id}"
    assert first == second
    assert len(service.state["tags"][parent]) == 1
    assert len(service.state["triggers"][parent]) == 1


def test_ensure_adsense_tag_creates_html_tag_with_publisher_id():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    tag_id = gtm.ensure_adsense_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        publisher_id="ca-pub-1234567890123456",
    )

    parent = f"accounts/222/containers/{container.container_id}/workspaces/{workspace.id}"
    created_tag = service.state["tags"][parent][0]
    assert created_tag["tagId"] == tag_id
    assert created_tag["type"] == "html"
    html_param = next(p for p in created_tag["parameter"] if p["key"] == "html")
    assert "ca-pub-1234567890123456" in html_param["value"]
    assert "pagead2.googlesyndication.com" in html_param["value"]
    assert created_tag["firingTriggerId"] == [service.state["triggers"][parent][0]["triggerId"]]


def test_ensure_adsense_tag_is_idempotent():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    first = gtm.ensure_adsense_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        publisher_id="ca-pub-1234567890123456",
    )
    second = gtm.ensure_adsense_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        publisher_id="ca-pub-1234567890123456",
    )

    parent = f"accounts/222/containers/{container.container_id}/workspaces/{workspace.id}"
    assert first == second
    assert len(service.state["tags"][parent]) == 1


def test_ensure_adsense_tag_reuses_all_pages_trigger_from_ga4_setup():
    """GA4 태그가 이미 만들어 둔 'All Pages' 트리거를 재사용해야 한다 — 트리거를

    또 만들면 GTM에 중복 pageview 트리거가 쌓인다."""

    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    gtm.ensure_ga4_config_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        measurement_id="G-ABC123",
    )
    gtm.ensure_adsense_tag(
        service,
        account_id="222",
        container_id=container.container_id,
        workspace_id=workspace.id,
        publisher_id="ca-pub-1234567890123456",
    )

    parent = f"accounts/222/containers/{container.container_id}/workspaces/{workspace.id}"
    assert len(service.state["triggers"][parent]) == 1


def test_publish_workspace_returns_version_id():
    service = FakeGtmService()
    container = gtm.find_or_create_container(service, account_id="222", name="dice-art")
    workspace = gtm.get_default_workspace(service, account_id="222", container_id=container.container_id)

    version_id = gtm.publish_workspace(
        service, account_id="222", container_id=container.container_id, workspace_id=workspace.id
    )

    assert version_id is not None
    assert isinstance(version_id, str)
