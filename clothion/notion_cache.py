from typing import Dict, List

from notion_client import APIResponseError  # noqa: F401
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from sqlalchemy.orm import Session

from clothion.database import crud, models


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


def get_data(db: Session, table: models.Table, reset_cache: bool = False, update_cache: bool = True) -> List[Dict]:
    """Retrieve the data for this table.

    The data is cached on the DB for fast retrieval and custom queries and
    filters.
    When this function is called, we call the Notion API to get only the latest
    changes that are not in the cache yet. If the cache is up-to-date, fine !
    And we return the data retrieved.

    Args:
        db (Session): DB Session to use for calling the DB.
        table (models.Table): Table for which we should retrieve the data.
        reset_cache (bool): If set to `True`, delete the local cache of the
            table, and retrieve everything from Notion API.
        update_cache (bool): If set to `False`, this method will not
            try to update the cache using the Notion API. Faster, but
            potentially not up-to-date. Defaults to `True`.

    Returns:
        List[Dict]: Data from the Notion table.
    """
    if reset_cache:
        crud.delete_elements_of_table(db, table.id)
        update_cache = True

    if update_cache:
        # Get the latest element to know from which date to retrieve stuff
        db_latest_element = crud.last_table_element(db, table.id) if not reset_cache else None

        filter_kwargs = {}
        if db_latest_element is not None:
            filter_kwargs = {
                "filter": {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {"after": db_latest_element.last_edited.isoformat()},
                }
            }

        # Call the Notion API to retrieve any elements newer than that date
        notion = Client(auth=table.integration.token)
        all_elements = []
        for elements in iterate_paginated_api(notion.databases.query, database_id=table.table_id, **filter_kwargs):
            all_elements.extend(elements)

        # Add or update all the newly edited properties in our DB
        for element in all_elements:
            # Check if this element already exists in our DB
            db_element = crud.get_element_by_notion_id(db, element["id"])

            if db_element is None:
                # Create it in our DB
                db_element = crud.create_element(
                    db, element["id"], table.id, element["last_edited_time"], element["properties"]
                )
            else:
                # Update it in our DB
                db_element = crud.update_element(db, db_element, element["last_edited_time"], element["properties"])

    return extract_data_from_db(db, table.id)


def get_schema(db: Session, table: models.Table) -> Dict:
    """Retrieve the schema of this table.

    This method check our DB to see if we can extract the schema from cached
    element. Only if nothing is in there we call the Notion API.

    Args:
        db (Session): DB Session to use for calling the DB.
        table (models.Table): Table for which we should retrieve the schema.

    Returns:
        Dict: Dictionary where the keys are the name of each attribute, and the
            values are the type of the attribute.
    """
    # Try to retrieve an element from the DB for this table
    db_latest_element = crud.last_table_element(db, table.id)

    if db_latest_element is None:
        # No data cached, get the schema from the Notion API
        notion = Client(auth=table.integration.token)
        notion_db = notion.databases.retrieve(database_id=table.table_id)
        return {name: prop["type"] for name, prop in notion_db["properties"].items()}
    else:
        # We have some data, use this to create the schema
        return {
            attr.name: attr.type
            for attr in [
                *db_latest_element.boolean_attributes,
                *db_latest_element.date_attributes,
                *db_latest_element.number_attributes,
                *db_latest_element.string_attributes,
                *db_latest_element.multi_attributes,
            ]
        }
