import os

import pytest
from fastapi.testclient import TestClient

from . import mock_notion_api  # noqa: F401 (just importing it will monkey-patch the notion API !)
from .utils import create_table


# Before importing clothion, set some options specifically for testing
# Importing clothion will load the configuration, so this should be done before !
os.environ["CLOTHION_DB"] = "memory"


import clothion  # noqa: E402


@pytest.fixture
def client():
    # Create the tables for the in-memory DB
    clothion.database.crud.create_tables()

    yield TestClient(clothion.app)


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
    form_data = {"integration": "token#1", "table": "id#1"}
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
    form_data = {"integration": "token#2", "table": "id#2"}
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
    form_data = {"integration": "token#3", "table": "id#3"}
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
    form_data = {"integration": "token#4", "table": "id#4"}
    response = client.post("/create", data=form_data)
    assert response.status_code == 200
    integration_id, table_id = response.url.path.strip("/").split("/")

    # Then, try to create a new integration but the same table
    form_data["integration"] = "token#4-2"
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
    integration_id, table_id = create_table(client, "token#5", "table_with_basic_data")

    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_data_handle_api_error(client):
    integration_id, table_id = create_table(client, "token#6", "table_api_error")

    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 404


def test_access_data_cached_after_first_call(client):
    integration_id, table_id = create_table(client, "token#7", "table_filter_call_no_data")

    # First call populate the cache
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call to Notion API returns nothing, but we still get full data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_data_new_element_on_second_call(client):
    integration_id, table_id = create_table(client, "token#8", "table_filter_call_new_data")

    # First call get the basic data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call assume user added an element later, so Notion API returns it
    # and we should get the full, updated data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data
    assert {"my_title": "Element 3", "price": -22} in data


def test_access_data_updated_element_on_second_call(client):
    integration_id, table_id = create_table(client, "token#9", "table_filter_call_updated_data")

    # First call get the basic data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # Second call assume user updated an element later, so Notion API returns
    # it and we should get the updated data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 0} in data


def test_access_data_reset_cache(client):
    integration_id, table_id = create_table(client, "token#10", "table_filter_call_crash_normal_call_updates")

    # First call get the basic data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # If the Mock Notion API is called a second time (with filter), it crashes
    # and fails the test. But we set `reset_cache` to `True`, forcing to
    # re-query the whole table (and observe the change in price as well)
    response = client.get(f"/{integration_id}/{table_id}/data?reset_cache=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 25} in data
    assert {"my_title": "Element 2", "price": 51} in data


def test_access_data_only_cache_on_existing_data(client):
    integration_id, table_id = create_table(client, "token#11", "table_filter_call_crash_normal_call_updates_2")

    # First call get the basic data
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data

    # If the Mock Notion API is called a second time (with filter), it crashes
    # and fails the test. But we set `update_cache` to `False`, which makes no
    # call to the Notion API and use the local cache instead (so the price
    # doesn't change)
    response = client.get(f"/{integration_id}/{table_id}/data?update_cache=false")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {"my_title": "Element 1", "price": 56} in data
    assert {"my_title": "Element 2", "price": 98} in data


def test_access_data_only_cache_on_no_data(client):
    integration_id, table_id = create_table(client, "token#12", "table_call_crash")

    # If the Mock Notion API is called, it crashes and fails the test.
    # But we set `update_cache` to `False`, so the Notion API is not called at all
    response = client.get(f"/{integration_id}/{table_id}/data?update_cache=false")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_access_data_full_data_range(client):
    integration_id, table_id = create_table(client, "token#13", "table_full_data")

    response = client.get(f"/{integration_id}/{table_id}/data")
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
    assert data[0]["created_at"] == "2023-05-07T14:02:00"
    assert data[0]["created_by"] == "111"
    assert data[0]["edited_at"] == "2023-05-07T14:08:00"
    assert data[0]["edited_by"] == "111"
    assert data[0]["rich_text"] == "Such a bore"
    assert data[0]["select"] == "Option 1"
    assert data[0]["multi_select"] == ["Opt1", "Opt2"]
    assert data[0]["status"] == "Not done"
    assert data[0]["date"] == "2023-05-08T10:00:00"
    assert data[0]["people"] == ["111"]
    assert data[0]["files"] == ["img.png"]


def test_get_schema_no_cache(client):
    integration_id, table_id = create_table(client, "token#14", "table_schema_full_data")

    response = client.get(f"/{integration_id}/{table_id}/schema")
    assert response.status_code == 200
    data = response.json()

    assert "created_at" in data and data["created_at"] == "created_time"
    assert "status_attr" in data and data["status_attr"] == "status"
    assert "rich_text_attr" in data and data["rich_text_attr"] == "rich_text"
    assert "edited_at" in data and data["edited_at"] == "last_edited_time"
    assert "url_attr" in data and data["url_attr"] == "url"
    assert "checkbox_attr" in data and data["checkbox_attr"] == "checkbox"
    assert "multi_select_attr" in data and data["multi_select_attr"] == "multi_select"
    assert "select_attr" in data and data["select_attr"] == "select"
    assert "people_attr" in data and data["people_attr"] == "people"
    assert "phone" in data and data["phone"] == "phone_number"
    assert "date_attr" in data and data["date_attr"] == "date"
    assert "number_attr" in data and data["number_attr"] == "number"
    assert "relation_attr" in data and data["relation_attr"] == "relation"
    assert "created_by_attr" in data and data["created_by_attr"] == "created_by"
    assert "edited_by" in data and data["edited_by"] == "last_edited_by"
    assert "email_attr" in data and data["email_attr"] == "email"
    assert "files_attr" in data and data["files_attr"] == "files"
    assert "formula_attr" in data and data["formula_attr"] == "formula"
    assert "title_attr" in data and data["title_attr"] == "title"
    assert "rollup" not in data


def test_get_schema_from_cache(client):
    integration_id, table_id = create_table(client, "token#15", "table_with_basic_data")

    # Access the data to fill our cache
    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 200

    # Then get the schema. The Mock Notion API will crash if called for this table,
    # but since we will extract it from our cache, the API will not be called
    response = client.get(f"/{integration_id}/{table_id}/schema")
    assert response.status_code == 200
    data = response.json()
    assert "my_title" in data and data["my_title"] == "title"
    assert "price" in data and data["price"] == "number"
