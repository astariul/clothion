from typing import Dict, List

from notion_client import APIResponseError  # noqa: F401
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from sqlalchemy.orm import Session

from clothion.database import crud


def extract_data_from_db(db: Session, db_table_id: int) -> List[Dict]:
    """Helper function that takes care of extracting the DB data and convert it
    into JSON data.

    Args:
        db (Session): DB Session to use for calling the DB.
        db_table_id (int): ID of the Table from which to extract the data.

    Returns:
        List[Dict]: JSON data corresponding to this table.
    """
    db_elements = crud.get_elements_of_table(db, db_table_id)

    data = []
    for element in db_elements:
        attributes = {}

        for attr in element.boolean_attributes:
            attributes[attr.name] = attr.value
        for attr in element.date_attributes:
            attributes[attr.name] = attr.value
        for attr in element.number_attributes:
            attributes[attr.name] = attr.value
        for attr in element.string_attributes:
            attributes[attr.name] = attr.value
        for attr in element.multi_attributes:
            attributes[attr.name] = [p.text for p in attr.parts]

        data.append(attributes)

    return data


def get_data(
    db: Session, token: str, table_id: str, db_table_id: int, reset_cache: bool = False, update_cache: bool = True
) -> List[Dict]:
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
        db_table_id (int): ID of the Table in our DB.
        reset_cache (bool): If set to `True`, delete the local cache of the
            table, and retrieve everything from Notion API.
        update_cache (bool): If set to `False`, this method will not
            try to update the cache using the Notion API. Faster, but
            potentially not up-to-date. Defaults to `True`.

    Returns:
        List[Dict]: Data from the Notion table.
    """
    if reset_cache:
        crud.delete_elements_of_table(db, db_table_id)
        update_cache = True

    if update_cache:
        # Get the latest element to know from which date to retrieve stuff
        db_latest_element = crud.last_table_element(db, db_table_id) if not reset_cache else None

        filter_kwargs = {}
        if db_latest_element is not None:
            filter_kwargs = {
                "filter": {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {"after": db_latest_element.last_edited.isoformat()},
                }
            }

        # Call the Notion API to retrieve any elements newer than that date
        notion = Client(auth=token)
        all_elements = []
        for elements in iterate_paginated_api(notion.databases.query, database_id=table_id, **filter_kwargs):
            all_elements.extend(elements)

        # Add or update all the newly edited properties in our DB
        for element in all_elements:
            # Check if this element already exists in our DB
            db_element = crud.get_element_by_notion_id(db, element["id"])

            if db_element is None:
                # Create it in our DB
                db_element = crud.create_element(
                    db, element["id"], db_table_id, element["last_edited_time"], element["properties"]
                )
            else:
                # Update it in our DB
                db_element = crud.update_element(db, db_element, element["last_edited_time"], element["properties"])

    return extract_data_from_db(db, db_table_id)
