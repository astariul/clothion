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
    integration_id, table_id = create_table(client, "token#5", "table_api_error")

    response = client.get(f"/{integration_id}/{table_id}/data")
    assert response.status_code == 404
