from __future__ import annotations

from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v25.resources.types.conversion_action import ConversionAction
from google.ads.googleads.v25.services.types.conversion_action_service import (
    MutateConversionActionResult,
    MutateConversionActionsResponse,
)
from google.ads.googleads.v25.services.types.google_ads_service import GoogleAdsRow

import project_lens.google.ads as ads


class FakeGoogleAdsService:
    def __init__(self, existing_rows):
        self._existing_rows = existing_rows
        self.search_calls = []

    def search(self, customer_id, query):
        self.search_calls.append((customer_id, query))
        return list(self._existing_rows)


class FakeConversionActionService:
    def __init__(self):
        self.create_calls = []
        self._next_id = 1000

    def mutate_conversion_actions(self, customer_id, operations):
        self.create_calls.append((customer_id, operations))
        self._next_id += 1
        operation = operations[0]
        resource_name = f"customers/{customer_id}/conversionActions/{self._next_id}"
        return MutateConversionActionsResponse(
            results=[MutateConversionActionResult(resource_name=resource_name)]
        )


class FakeGoogleAdsClient:
    def __init__(self, existing_rows=()):
        self.ga_service = FakeGoogleAdsService(existing_rows)
        self.conversion_action_service = FakeConversionActionService()

    def get_service(self, name):
        if name == "GoogleAdsService":
            return self.ga_service
        if name == "ConversionActionService":
            return self.conversion_action_service
        raise AssertionError(f"unexpected service: {name}")


def test_find_or_create_conversion_action_creates_when_missing():
    client = FakeGoogleAdsClient(existing_rows=[])

    result = ads.find_or_create_conversion_action(
        client, customer_id="1112223333", name="kokoa-lab-dice-art purchase"
    )

    assert client.conversion_action_service.create_calls, "생성 API가 호출됐어야 함"
    assert result.resource_name.startswith("customers/1112223333/conversionActions/")
    assert result.name == "kokoa-lab-dice-art purchase"

    operation = client.conversion_action_service.create_calls[0][1][0]
    assert operation.create.name == "kokoa-lab-dice-art purchase"
    assert operation.create.type_.name == "WEBPAGE"
    assert operation.create.status.name == "ENABLED"
    assert operation.create.category.name == "DEFAULT"


def test_find_or_create_conversion_action_reuses_existing():
    existing = GoogleAdsRow(
        conversion_action=ConversionAction(
            id=555,
            resource_name="customers/1112223333/conversionActions/555",
            name="kokoa-lab-dice-art purchase",
        )
    )
    client = FakeGoogleAdsClient(existing_rows=[existing])

    result = ads.find_or_create_conversion_action(
        client, customer_id="1112223333", name="kokoa-lab-dice-art purchase"
    )

    assert result.id == "555"
    assert result.resource_name == "customers/1112223333/conversionActions/555"
    assert client.conversion_action_service.create_calls == []


def test_find_or_create_conversion_action_escapes_query_value():
    client = FakeGoogleAdsClient(existing_rows=[])

    ads.find_or_create_conversion_action(client, customer_id="111", name="it's a test")

    _, query = client.ga_service.search_calls[0]
    assert "it\\'s a test" in query


def test_find_or_create_conversion_action_wraps_api_error():
    class ExplodingService:
        def search(self, customer_id, query):
            raise GoogleAdsException(None, None, None, None)

    class ExplodingClient:
        def get_service(self, name):
            return ExplodingService()

    import pytest

    from project_lens.errors import GoogleAPIError

    with pytest.raises(GoogleAPIError):
        ads.find_or_create_conversion_action(ExplodingClient(), customer_id="111", name="x")
