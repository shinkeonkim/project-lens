from __future__ import annotations

from google.analytics.admin_v1beta.types import Account, DataStream, Property

import project_lens.google.ga4 as ga4


class FakeGa4Client:
    """AnalyticsAdminServiceClient을 흉내내는 인메모리 대역.

    실제 proto-plus 타입(Account/Property/DataStream)을 그대로 써서, ga4.py가
    실제 클라이언트 응답과 같은 형태의 속성 접근(.name, .display_name 등)에
    의존해도 검증되도록 한다.
    """

    def __init__(self):
        self.accounts = [Account(name="accounts/111", display_name="shinkeonkim")]
        self.properties: dict[str, list[Property]] = {}
        self.streams: dict[str, list[DataStream]] = {}
        self._next_id = 1000
        self.create_property_calls = 0
        self.create_data_stream_calls = 0

    def _next(self) -> int:
        self._next_id += 1
        return self._next_id

    def list_accounts(self):
        return self.accounts

    def list_properties(self, request: dict):
        parent = request["filter"].removeprefix("parent:")
        return list(self.properties.get(parent, []))

    def create_property(self, property: Property):
        self.create_property_calls += 1
        prop_id = self._next()
        created = Property(
            name=f"properties/{prop_id}",
            display_name=property.display_name,
            parent=property.parent,
        )
        self.properties.setdefault(property.parent, []).append(created)
        return created

    def list_data_streams(self, parent: str):
        return list(self.streams.get(parent, []))

    def create_data_stream(self, parent: str, data_stream: DataStream):
        self.create_data_stream_calls += 1
        stream_id = self._next()
        measurement_id = f"G-{stream_id}"
        created = DataStream(
            name=f"{parent}/dataStreams/{stream_id}",
            display_name=data_stream.display_name,
            type_=DataStream.DataStreamType.WEB_DATA_STREAM,
            web_stream_data=DataStream.WebStreamData(
                default_uri=data_stream.web_stream_data.default_uri,
                measurement_id=measurement_id,
            ),
        )
        self.streams.setdefault(parent, []).append(created)
        return created


def test_list_accounts():
    client = FakeGa4Client()
    accounts = ga4.list_accounts(client)
    assert accounts == [ga4.Ga4Account(id="111", display_name="shinkeonkim")]


def test_find_or_create_property_creates_when_missing():
    client = FakeGa4Client()
    prop = ga4.find_or_create_property(client, account_id="111", display_name="kokoa-lab-dice-art")

    assert client.create_property_calls == 1
    assert prop.name.startswith("properties/")


def test_find_or_create_property_is_idempotent():
    client = FakeGa4Client()
    first = ga4.find_or_create_property(client, account_id="111", display_name="kokoa-lab-dice-art")
    second = ga4.find_or_create_property(client, account_id="111", display_name="kokoa-lab-dice-art")

    assert client.create_property_calls == 1
    assert first == second


def test_find_or_create_web_stream_creates_when_missing():
    client = FakeGa4Client()
    prop = ga4.find_or_create_property(client, account_id="111", display_name="dice-art")

    stream = ga4.find_or_create_web_stream(
        client,
        property_name=prop.name,
        display_name="dice-art",
        default_uri="https://dice-art.example.com",
    )

    assert client.create_data_stream_calls == 1
    assert stream.measurement_id.startswith("G-")


def test_find_or_create_web_stream_is_idempotent_by_uri():
    client = FakeGa4Client()
    prop = ga4.find_or_create_property(client, account_id="111", display_name="dice-art")

    first = ga4.find_or_create_web_stream(
        client, property_name=prop.name, display_name="dice-art", default_uri="https://dice-art.example.com"
    )
    second = ga4.find_or_create_web_stream(
        client, property_name=prop.name, display_name="dice-art", default_uri="https://dice-art.example.com"
    )

    assert client.create_data_stream_calls == 1
    assert first == second
