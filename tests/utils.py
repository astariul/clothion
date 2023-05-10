from typing import Tuple

from fastapi.testclient import TestClient


def create_table(client: TestClient, token: str, table_id: str) -> Tuple[str, str]:
    """Helper function that create a table with the given token and table ID,
    and returns the identifiers of the path (integration ID and table ID).

    Args:
        client (TestClient): The TestClient to use to create the table.
        token (str): The token to register.
        table_id (str): The Table ID to register.

    Returns:
        Tuple[str, str]: the resulting path identifiers (integration & table).
    """
    form_data = {"integration": token, "table": table_id}
    response = client.post("/create", data=form_data)
    assert response.status_code == 200
    integration_id, table_id = response.url.path.strip("/").split("/")
    return (integration_id, table_id)
