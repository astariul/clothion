import pytest
from fastapi.testclient import TestClient

import clothion


@pytest.fixture
def client():
    yield TestClient(clothion.app)


def test_package_has_version():
    assert len(clothion.__version__) > 0


def test_version_route(client):
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == clothion.__version__
