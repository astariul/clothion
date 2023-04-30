import sys

import pytest
from fastapi.testclient import TestClient


# Before importing clothion, set some options specifically for testing
# Importing clothion will load the configuration, so this should be done before !
sys.argv.append("db=memory")


import clothion  # noqa: E402


@pytest.fixture
def client():
    # Create the tables for the in-memory DB
    clothion.database.crud.create_tables()

    yield TestClient(clothion.app)


@pytest.fixture
def integration_id(client):
    # Register an integration
    integration = {"token": "secret_fixture"}
    response = client.post("/integration", json=integration)
    assert response.status_code == 200
    return response.json()["id"]


def test_package_has_version():
    assert len(clothion.__version__) > 0


def test_version_route(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == clothion.__version__


def test_register_integration_basic(client):
    integration = {"token": "secret#1"}
    response = client.post("/integration", json=integration)

    assert response.status_code == 200
    res = response.json()
    assert res["token"] == integration["token"]
    assert isinstance(res["id"], int)
    assert isinstance(res["tables"], list) and len(res["tables"]) == 0


def test_register_integration_exists_already(client):
    # Register an integration
    integration = {"token": "secret#2"}
    response = client.post("/integration", json=integration)
    assert response.status_code == 200

    # Try to register it again
    response = client.post("/integration", json=integration)

    assert response.status_code == 200
    res = response.json()
    assert res["token"] == integration["token"]
    assert isinstance(res["id"], int)
    assert isinstance(res["tables"], list) and len(res["tables"]) == 0


def test_read_integration_basic(client):
    # Register an integration
    integration = {"token": "secret#3"}
    response = client.post("/integration", json=integration)
    assert response.status_code == 200
    integration_id = response.json()["id"]

    # Read it
    response = client.get(f"/{integration_id}")
    assert response.status_code == 200
    res = response.json()
    assert res["token"] == integration["token"]
    assert res["id"] == integration_id
    assert isinstance(res["tables"], list) and len(res["tables"]) == 0


def test_read_integration_not_existing(client):
    response = client.get("/99999")
    assert response.status_code == 404


def test_register_table_basic(client, integration_id):
    table = {"table_id": "table#1"}
    response = client.post(f"/{integration_id}/table", json=table)

    assert response.status_code == 200
    res = response.json()
    assert res["table_id"] == table["table_id"]
    assert isinstance(res["id"], int)
    assert res["integration_id"] == integration_id


def test_read_tables_basic(client, integration_id):
    # Register 2 tables
    table_1 = {"table_id": "table#2"}
    response = client.post(f"/{integration_id}/table", json=table_1)
    assert response.status_code == 200
    table_1["id"] = response.json()["id"]
    table_1["integration_id"] = integration_id

    table_2 = {"table_id": "table#3"}
    response = client.post(f"/{integration_id}/table", json=table_2)
    assert response.status_code == 200
    table_2["id"] = response.json()["id"]
    table_2["integration_id"] = integration_id

    # Read the tables
    response = client.get(f"/{integration_id}/tables")

    assert response.status_code == 200
    res = response.json()
    assert len(res) >= 2
    assert table_1 in res
    assert table_2 in res
