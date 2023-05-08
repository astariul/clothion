from typing import Dict, List

from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from sqlalchemy.orm import Session


def get_data(db: Session, token: str, table_id: str, update_cache: bool = True) -> List[Dict]:
    """Retrieve the data for this table.

    The data is cached on the DB for fast retrieval and custom queries and
    filters.
    When this function is called, we call the Notion API to get only the latest
    changes that are not in the cache yet. If the cache is up-to-date, fine !
    And we return the data retrieved.

    Args:
        db (Session): DB Session to use for calling the DB.
        token (str): Integration token that has access to the Notion table.
        table_id (str): ID of the Notion table to get the data from.
        update_cache (bool): If set to `False`, this method will not
            try to update the cache using the Notion API. Faster, but
            potentially not up-to-date. Defaults to `True`.

    Returns:
        List[Dict]: Data from the Notion table.
    """
    # For now, nothing is cached locally, we always call the Notion API
    notion = Client(auth=token)
    properties = []
    for block in iterate_paginated_api(notion.databases.query, database_id=table_id):
        for b in block:
            properties.append(b["properties"])

    return properties
