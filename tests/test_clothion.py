import os
from datetime import datetime, timezone

import pytest
from dateutil.relativedelta import relativedelta
from fastapi.testclient import TestClient

from . import mock_notion_api  # noqa: F401 (just importing it will monkey-patch the notion API !)
from .utils import create_table, no_timezone_date


# Before importing clothion, set some options specifically for testing
# Importing clothion will load the configuration, so this should be done before !
os.environ["CLOTHION_DB"] = "memory"


import clothion  # noqa: E402


@pytest.fixture
def client():
    # Create the tables for the in-memory DB
    clothion.database.crud.create_tables()

    yield TestClient(clothion.app)


@pytest.fixture
def temporary_reduce_max_attributes():
    # Monkey-patch MAX_ATTRIBUTES to something smaller, for tests going over
    # this limit, without making the tests slower
    old_max_attributes = clothion.notion_cache.MAX_ATTRIBUTES
    clothion.notion_cache.MAX_ATTRIBUTES = 10

    yield None

    # Monkey-patch back to normal value after the test
    clothion.notion_cache.MAX_ATTRIBUTES = old_max_attributes


def test_package_has_version():
    assert len(clothion.__version__) > 0


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.template.name == "welcome.html"


def test_favion(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200


def test_version_route(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == clothion.__version__


def test_create_new_integration_new_table(client):
    form_data = {"integration": "secret_token", "table": "id#1"}
    response = client.post("/create", data=form_data)

    # We have one redirection, leading to our newly created resource
    assert len(response.history) == 1
    assert response.history[0].status_code == 301
    assert response.status_code == 200

    # The redirected resource path has both the integration ID and the table ID, base64-encoded
    url_parts = response.url.path.strip("/").split("/")
    assert len(url_parts) == 2
    integration_id, table_id = url_parts
    assert len(integration_id) == 6
    assert len(table_id) == 6


def test_create_existing_integration_existing_table(client):
    # First, create an integration and a table
    form_data = {"integration": "secret_token", "table": "id#2"}
    response = client.post("/create", data=form_data)
    assert response.status_code == 200
    integration_id, table_id = response.url.path.strip("/").split("/")

    # Then, try to recreate the exact same integration and table
    response = client.post("/create", data=form_data)

    # We should receive the exact same IDs
    assert response.status_code == 200
    integration_id_2, table_id_2 = response.url.path.strip("/").split("/")
    assert integration_id == integration_id_2
    assert table_id == table_id_2


def test_create_existing_integration_new_table(client):
    # First, create an integration and a table
    form_data = {"integration": "secret_token", "table": "id#3"}
    response = client.post("/create", data=form_data)
    assert response.status_code == 200
    integration_id, table_id = response.url.path.strip("/").split("/")

    # Then, try to create a new table for the same integration
    form_data["table"] = "id#3-2"
    response = client.post("/create", data=form_data)

    # We should receive the same ID for the integration, but a new ID for the table
    assert response.status_code == 200
    integration_id_2, table_id_2 = response.url.path.strip("/").split("/")
    assert integration_id == integration_id_2
    assert table_id != table_id_2


def test_create_new_integration_existing_table(client):
    # First, create an integration and a table
    form_data = {"integration": "secret_token", "table": "id#4"}
    response = client.post("/create", data=form_data)
    assert response.status_code == 200
    integration_id, table_id = response.url.path.strip("/").split("/")

    # Then, try to create a new integration but the same table
    form_data["integration"] = "secret_token#2"
    response = client.post("/create", data=form_data)

    # We should receive different ID for both the integration and the table
    # (because the table belong to a different integration !)
    assert response.status_code == 200
    integration_id_2, table_id_2 = response.url.path.strip("/").split("/")
    assert integration_id != integration_id_2
    assert table_id != table_id_2


def test_access_inexisting_resource(client):
    response = client.get("/000000/000000")
    assert response.status_code == 404
    assert response.template.name == "404.html"


def test_access_wrong_b64_resource(client):
    response = client.get("/1/1")
    assert response.status_code == 404
    assert response.template.name == "404.html"


def test_access_data_of_freshly_created_table(client):
    integration_id, table_id = create_table(client, "secret_token", "table_with_basic_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_inexisting_data(client):
    response = client.post("/000000/000000/data", json={})
    assert response.status_code == 404


def test_access_wrong_b64_data(client):
    response = client.post("/1/1/data", json={})
    assert response.status_code == 404


def test_access_data_handle_api_error(client):
    integration_id, table_id = create_table(client, "secret_token", "table_api_error")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 422


def test_access_data_cached_after_first_call(client):
    integration_id, table_id = create_table(client, "secret_token", "table_filter_call_no_data")

    # First call populate the cache
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call to Notion API returns nothing, but we still get full data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_data_new_element_on_second_call(client):
    integration_id, table_id = create_table(client, "secret_token", "table_filter_call_new_data")

    # First call get the basic data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call assume user added an element later, so Notion API returns it
    # and we should get the full, updated data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data
    assert {"my_title": "Element 3", "price": -22} in data


def test_access_data_updated_element_on_second_call(client):
    integration_id, table_id = create_table(client, "secret_token", "table_filter_call_updated_data")

    # First call get the basic data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call assume user updated an element later, so Notion API returns
    # it and we should get the updated data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 0} in data


def test_access_data_reset_cache(client):
    integration_id, table_id = create_table(client, "secret_token", "table_filter_call_crash_normal_call_updates")

    # First call get the basic data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # If the Mock Notion API is called a second time (with filter), it crashes
    # and fails the test. But we set `reset_cache` to `True`, forcing to
    # re-query the whole table (and observe the change in price as well)
    response = client.post(f"/{integration_id}/{table_id}/data", json={"reset_cache": True})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 25} in data
    assert {"my_title": "Element 2", "price": 51} in data


def test_access_data_only_cache_on_existing_data(client):
    integration_id, table_id = create_table(client, "secret_token", "table_filter_call_crash_normal_call_updates_2")

    # First call get the basic data
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # If the Mock Notion API is called a second time (with filter), it crashes
    # and fails the test. But we set `update_cache` to `False`, which makes no
    # call to the Notion API and use the local cache instead (so the price
    # doesn't change)
    response = client.post(f"/{integration_id}/{table_id}/data", json={"update_cache": False})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_data_only_cache_on_no_data(client):
    integration_id, table_id = create_table(client, "secret_token", "table_call_crash")

    # If the Mock Notion API is called, it crashes and fails the test.
    # But we set `update_cache` to `False`, so the Notion API is not called at all
    response = client.post(f"/{integration_id}/{table_id}/data", json={"update_cache": False})
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_access_data_full_data_range(client):
    integration_id, table_id = create_table(client, "secret_token", "table_full_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "My title"
    assert data[0]["checkbox"] is True
    assert data[0]["number"] == 2.5
    assert data[0]["url"] == "example.com"
    assert data[0]["email"] == "me@example.com"
    assert data[0]["phone"] == "010-3715-6565"
    assert data[0]["formula"] == "256"
    assert "relation" not in data[0]
    assert "rollup" not in data[0]
    assert data[0]["created_at"] == no_timezone_date("2023-05-07T14:02:00.000Z", as_str=True)
    assert data[0]["created_by"] == "111"
    assert data[0]["edited_at"] == no_timezone_date("2023-05-07T14:08:00.000Z", as_str=True)
    assert data[0]["edited_by"] == "111"
    assert data[0]["rich_text"] == "Such a bore"
    assert data[0]["select"] == "Option 1"
    assert data[0]["multi_select"] == ["Opt1", "Opt2"]
    assert data[0]["status"] == "Not done"
    assert data[0]["date"] == no_timezone_date("2023-05-08T10:00:00.000+09:00", as_str=True)
    assert data[0]["people"] == ["111"]
    assert data[0]["files"] == ["img.png"]


def test_access_data_utc_date(client):
    integration_id, table_id = create_table(client, "secret_token", "table_with_tz_dates")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] == "UTC"
    assert data[0]["x"] == no_timezone_date("2023-05-27T10:03:01.264216", as_str=True)
    assert data[0]["created_at"] == no_timezone_date("2023-05-27T10:20:09.323332+00:00", as_str=True)
    assert data[0]["edited_at"] == no_timezone_date("2023-05-27T10:20:09.323332+09:00", as_str=True)


def test_access_data_empty_data_range(client):
    integration_id, table_id = create_table(client, "secret_token", "table_empty_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["title"] is None
    assert data[0]["checkbox"] is False
    assert data[0]["number"] is None
    assert data[0]["url"] is None
    assert data[0]["email"] is None
    assert data[0]["phone"] is None
    assert data[0]["formula"] == "0"
    assert "relation" not in data[0]
    assert "rollup" not in data[0]
    assert data[0]["created_at"] == "2023-05-07T14:02:00"
    assert data[0]["created_by"] == "111"
    assert data[0]["edited_at"] == "2023-05-07T14:08:00"
    assert data[0]["edited_by"] == "111"
    assert data[0]["rich_text"] is None
    assert data[0]["select"] is None
    assert data[0]["multi_select"] is None
    assert data[0]["status"] == "Not done"
    assert data[0]["date"] is None
    assert data[0]["people"] is None
    assert data[0]["files"] is None


def test_access_too_much_data(client, temporary_reduce_max_attributes):
    integration_id, table_id = create_table(client, "secret_token", "table_too_much")

    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 413


def test_get_schema_no_cache(client):
    integration_id, table_id = create_table(client, "secret_token", "table_schema_full_data")

    response = client.get(f"/{integration_id}/{table_id}/schema")
    assert response.status_code == 200
    data = response.json()

    assert data.pop("created_at", None) == "created_time"
    assert data.pop("status_attr", None) == "status"
    assert data.pop("rich_text_attr", None) == "rich_text"
    assert data.pop("edited_at", None) == "last_edited_time"
    assert data.pop("url_attr", None) == "url"
    assert data.pop("checkbox_attr", None) == "checkbox"
    assert data.pop("multi_select_attr", None) == "multi_select"
    assert data.pop("select_attr", None) == "select"
    assert data.pop("people_attr", None) == "people"
    assert data.pop("phone", None) == "phone_number"
    assert data.pop("date_attr", None) == "date"
    assert data.pop("number_attr", None) == "number"
    assert "relation_attr" not in data
    assert data.pop("created_by_attr", None) == "created_by"
    assert data.pop("edited_by", None) == "last_edited_by"
    assert data.pop("email_attr", None) == "email"
    assert data.pop("files_attr", None) == "files"
    assert data.pop("formula_attr", None) == "formula"
    assert data.pop("title_attr", None) == "title"
    assert len(data) == 0


def test_get_schema_from_cache(client):
    integration_id, table_id = create_table(client, "secret_token", "table_with_basic_data")

    # Access the data to fill our cache
    response = client.post(f"/{integration_id}/{table_id}/data", json={})
    assert response.status_code == 200

    # Then get the schema. The Mock Notion API will crash if called for this table,
    # but since we will extract it from our cache, the API will not be called
    response = client.get(f"/{integration_id}/{table_id}/schema")
    assert response.status_code == 200
    data = response.json()
    assert "my_title" in data and data["my_title"] == "title"
    assert "price" in data and data["price"] == "number"


def test_access_inexisting_schema(client):
    response = client.get("/000000/000000/schema")
    assert response.status_code == 404


def test_access_wrong_b64_schema(client):
    response = client.get("/1/1/schema")
    assert response.status_code == 404


def test_get_schema_handle_api_error(client):
    integration_id, table_id = create_table(client, "secret_token", "table_api_error")

    response = client.get(f"/{integration_id}/{table_id}/schema")
    assert response.status_code == 422


def test_refresh_page(client):
    integration_id, table_id = create_table(client, "secret_token", "id#17")

    response = client.get(f"/{integration_id}/{table_id}/refresh")
    assert response.status_code == 200
    assert response.template.name == "refresh.html"


def test_access_inexisting_refresh(client):
    response = client.get("/000000/000000/refresh")
    assert response.status_code == 404
    assert response.template.name == "404.html"


def test_access_wrong_b64_refresh(client):
    response = client.get("/1/1/refresh")
    assert response.status_code == 404
    assert response.template.name == "404.html"


def test_calculate_data_sum(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_number_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "sum"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"price": 56.5 + 98 + -13, "quantity": 3 + 0} in data


def test_data_wrong_parameters(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_data_sum")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "wrong"})
    assert response.status_code == 422


def test_calculate_data_min(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_number_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "min"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"price": -13, "quantity": 0} in data


def test_calculate_data_max(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_number_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "max"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"price": 98, "quantity": 3} in data


def test_calculate_data_average(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_number_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "average"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"price": (56.5 + 98 + -13) / 3, "quantity": (3 + 0) / 2} in data


def test_calculate_data_count(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "count"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"my_title": 6, "email": 7, "price": 6, "day_of": 4, "ckbox": 8, "choices": 6} in data


def test_calculate_data_unique_count(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"calculate": "count_unique"})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert {"my_title": 5, "email": 5, "price": 4, "day_of": 3, "ckbox": 2, "choices": 4} in data


def test_filter_data_wrong_attribute_name(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"check-box": {"is": True}}})
    assert response.status_code == 422


def test_filter_data_wrong_filter_name(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"wrong_is": True}}})
    assert response.status_code == 422


def test_filter_data_empty_table(client):
    integration_id, table_id = create_table(client, "secret_token", "empty_table")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is": True}}})
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_filter_data_boolean_is_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get values that are True
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is": True}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["ckbox"] is True for x in data)

    # Get values that are False
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is": False}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 6
    assert all(x["ckbox"] is False for x in data)


@pytest.mark.parametrize("value", [47, "str"])
@pytest.mark.parametrize("op", ["is", "is_not"])
def test_filter_data_boolean_is_is_not_wrong_type(client, value, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {op: value}}})
    assert response.status_code == 422


def test_filter_data_number_is_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get int values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is": 56.6}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert all(x["price"] == 56.6 for x in data)

    # Get float values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is": 699}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["price"] == 699 for x in data)

    # Get values that doesn't exist
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is": -89}}})
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.parametrize("value", [True, "str"])
@pytest.mark.parametrize("op", ["is", "is_not"])
def test_filter_data_number_is_is_not_wrong_type(client, value, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {op: value}}})
    assert response.status_code == 422


def test_filter_data_string_is_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get value
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"email": {"is": "me5@lol.com"}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(x["email"] == "me5@lol.com" for x in data)

    # Get values that doesn't exist
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"my_title": {"is": "me5@lol.com"}}})
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.parametrize("value", [True, 65])
@pytest.mark.parametrize("op", ["is", "is_not"])
def test_filter_data_string_is_wrong_type(client, value, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"my_title": {op: value}}})
    assert response.status_code == 422


def test_filter_data_date_is_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get value
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"is": "2023-05-08T10:00:00.000+09:00"}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["day_of"] == no_timezone_date("2023-05-08T10:00:00.000+09:00", as_str=True) for x in data)

    # Get values that doesn't exist
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"is": "1999-05-08T10:00:00.000+09:00"}}}
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.parametrize("value", [True, 65, "not_a_date"])
@pytest.mark.parametrize("op", ["is", "is_not"])
def test_filter_data_date_is_wrong_type(client, value, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {op: value}}})
    assert response.status_code == 422


@pytest.mark.parametrize("op", ["is", "is_not"])
def test_filter_data_multistring_cant_use_is_is_not(client, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"choices": {op: "Opt1"}}})
    assert response.status_code == 422


def test_filter_data_boolean_is_not_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get values that are not True
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is_not": True}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 6
    assert all(x["ckbox"] is False for x in data)

    # Get values that are not False
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is_not": False}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["ckbox"] is True for x in data)


def test_filter_data_number_is_not_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get int values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is_not": 56.6}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 5
    assert all(x["price"] != 56.6 for x in data)

    # Get float values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is_not": 699}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4
    assert all(x["price"] != 699 for x in data)

    # Get values that doesn't exist
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"is_not": -89}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 6
    assert all(x["price"] != -89 for x in data)


def test_filter_data_string_is_not_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get value
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"email": {"is_not": "me5@lol.com"}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4
    assert all(x["email"] != "me5@lol.com" for x in data)

    # Get values that doesn't exist
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"my_title": {"is_not": "me5@lol.com"}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 6
    assert all(x["my_title"] != "me5@lol.com" for x in data)


def test_filter_data_date_is_not_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get value
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"is_not": "2023-05-08T10:00:00.000+09:00"}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["day_of"] != no_timezone_date("2023-05-08T10:00:00.000+09:00", as_str=True) for x in data)

    # Get values that doesn't exist
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"is_not": "1999-05-08T10:00:00.000+09:00"}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4
    assert all(x["day_of"] != no_timezone_date("1999-05-08T10:00:00.000+09:00", as_str=True) for x in data)


def test_filter_data_boolean_cant_use_is_empty(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"ckbox": {"is_empty": True}}})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "attr_to_filter, expected_n_empty", [("day_of", 4), ("price", 2), ("my_title", 2), ("choices", 2)]
)
def test_filter_data_is_empty_basic(client, attr_to_filter, expected_n_empty):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {attr_to_filter: {"is_empty": True}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == expected_n_empty
    assert all(x[attr_to_filter] is None for x in data)

    # Get non-empty values
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {attr_to_filter: {"is_empty": False}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 8 - expected_n_empty  # 8 is the total number of elements in this table
    assert all(x[attr_to_filter] is not None for x in data)


@pytest.mark.parametrize("value", [65, "not_a_bool"])
def test_filter_data_is_empty_wrong_value_type(client, value):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"is_empty": value}}})
    assert response.status_code == 422


def test_filter_data_date_after_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # The results shouldn't include the date itself (because it's AFTER X)
    date = "2023-05-08T10:00:00.000+09:00"
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"after": date}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert all(no_timezone_date(x["day_of"]) > no_timezone_date(date) for x in data)


@pytest.mark.parametrize("attr", ["price", "my_title", "choices", "ckbox"])
@pytest.mark.parametrize("op", ["after", "on_or_after", "before", "on_or_before"])
def test_filter_data_date_op_wrong_attribute(client, attr, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {attr: {op: "2023-05-08T10:00:00.000+09:00"}}}
    )
    assert response.status_code == 422


def test_filter_data_date_on_or_after_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # The results should include the date itself
    date = "2023-05-08T10:00:00.000+09:00"
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"on_or_after": date}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(no_timezone_date(x["day_of"]) >= no_timezone_date(date) for x in data)


def test_filter_data_date_before_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # The results shouldn't include the date itself (because it's BEFORE X)
    date = "2023-05-08T10:00:00.000+09:00"
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"before": date}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert all(no_timezone_date(x["day_of"]) < no_timezone_date(date) for x in data)


def test_filter_data_date_on_or_before_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # The results should include the date itself
    date = "2023-05-08T10:00:00.000+09:00"
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"day_of": {"on_or_before": date}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(no_timezone_date(x["day_of"]) <= no_timezone_date(date) for x in data)


@pytest.mark.parametrize("attr", ["price", "my_title", "choices", "ckbox"])
@pytest.mark.parametrize("op", ["past", "next", "this"])
def test_filter_data_date_past_next_this_wrong_attribute(client, attr, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {attr: {op: "week"}}})
    assert response.status_code == 422


@pytest.mark.parametrize("period, n_expected_results", [("week", 2), ("month", 3), ("year", 4)])
def test_filter_data_date_past_basic(client, period, n_expected_results):
    integration_id, table_id = create_table(client, "secret_token", "table_with_dates")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"d": {"past": period}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == n_expected_results

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "week":
        start = now - relativedelta(weeks=1)
    elif period == "month":
        start = now - relativedelta(months=1)
    elif period == "year":
        start = now - relativedelta(years=1)

    assert all(start <= no_timezone_date(x["d"]) <= now for x in data)


@pytest.mark.parametrize("period, n_expected_results", [("week", 1), ("month", 2), ("year", 3)])
def test_filter_data_date_next_basic(client, period, n_expected_results):
    integration_id, table_id = create_table(client, "secret_token", "table_with_dates")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"d": {"next": period}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == n_expected_results

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "week":
        end = now + relativedelta(weeks=1)
    elif period == "month":
        end = now + relativedelta(months=1)
    elif period == "year":
        end = now + relativedelta(years=1)

    assert all(now <= no_timezone_date(x["d"]) <= end for x in data)


@pytest.mark.parametrize("op", ["past", "next", "this"])
@pytest.mark.parametrize("period", ["decade", "minute"])
def test_filter_data_date_past_next_this_wrong_period(client, op, period):
    integration_id, table_id = create_table(client, "secret_token", "table_with_dates")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"d": {op: period}}})
    assert response.status_code == 422


@pytest.mark.parametrize("period, n_expected_results", [("week", 2), ("month", 4), ("year", 6)])
def test_filter_data_date_this_basic(client, period, n_expected_results):
    integration_id, table_id = create_table(client, "secret_token", "table_with_dates_2")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"d": {"this": period}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == n_expected_results

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    if period == "week":
        start = today - relativedelta(days=today.weekday())
        delta = relativedelta(weeks=1)
    elif period == "month":
        start = today.replace(day=1)
        delta = relativedelta(months=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
        delta = relativedelta(years=1)

    assert all(start <= no_timezone_date(x["d"]) <= start + delta for x in data)


@pytest.mark.parametrize("attr", ["day_of", "my_title", "choices", "ckbox"])
@pytest.mark.parametrize("op", ["greater_than", "less_than", "greater_or_equal", "less_or_equal"])
def test_filter_data_number_comp_wrong_attribute(client, attr, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {attr: {op: 42}}})
    assert response.status_code == 422


@pytest.mark.parametrize("op", ["greater_than", "less_than", "greater_or_equal", "less_or_equal"])
@pytest.mark.parametrize("value", ["string", True])
def test_filter_data_number_comp_wrong_value_type(client, op, value):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {op: value}}})
    assert response.status_code == 422


def test_filter_data_number_greater_than_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"greater_than": 56.5}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(x["price"] > 56.5 for x in data)


def test_filter_data_number_less_than_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"less_than": 56.5}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert all(x["price"] < 56.5 for x in data)


def test_filter_data_number_greater_or_equal_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"greater_or_equal": 56.5}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 5
    assert all(x["price"] >= 56.5 for x in data)


def test_filter_data_number_less_or_equal_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"price": {"less_or_equal": 56.5}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(x["price"] <= 56.5 for x in data)


@pytest.mark.parametrize("attr", ["price", "day_of", "choices", "ckbox"])
@pytest.mark.parametrize("op", ["starts_with", "ends_with"])
def test_filter_data_string_op_wrong_attribute(client, attr, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {attr: {op: "test"}}})
    assert response.status_code == 422


@pytest.mark.parametrize("op", ["starts_with", "ends_with", "contains", "does_not_contain"])
@pytest.mark.parametrize("value", [45, True])
def test_filter_data_string_op_wrong_value_type(client, op, value):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"my_title": {op: value}}})
    assert response.status_code == 422


def test_filter_data_string_starts_with_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"email": {"starts_with": "me5"}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all(x["email"].startswith("me5") for x in data)


def test_filter_data_string_ends_with_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"my_title": {"ends_with": "4"}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert all(x["my_title"].endswith("4") for x in data)


@pytest.mark.parametrize("attr", ["price", "day_of", "ckbox"])
@pytest.mark.parametrize("op", ["contains", "does_not_contain"])
def test_filter_data_contains_wrong_attribute(client, attr, op):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    # Get empty values
    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {attr: {op: "test"}}})
    assert response.status_code == 422


def test_filter_data_string_contains_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(f"/{integration_id}/{table_id}/data", json={"filter": {"email": {"contains": "5@"}}})
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 3
    assert all("5@" in x["email"] for x in data)


def test_filter_data_string_does_not_contain_basic(client):
    integration_id, table_id = create_table(client, "secret_token", "table_for_general_data")

    response = client.post(
        f"/{integration_id}/{table_id}/data", json={"filter": {"email": {"does_not_contain": "5@"}}}
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4
    assert all("5@" not in x["email"] for x in data)
