import json
from collections import defaultdict
from typing import Dict, List, Literal

from notion_client import APIResponseError  # noqa: F401
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from pydantic import BaseModel
from sqlalchemy.orm import Session

from clothion.database import crud, models


MAX_ATTRIBUTES = 500


class TooMuchAttributes(Exception):
    pass


class Parameters(BaseModel):
    reset_cache: bool = False
    update_cache: bool = True
    calculate: Literal[None, "sum", "min", "max", "average", "count"] = None


def extract_data_from_db(db: Session, db_table_id: int, parameters: Parameters) -> List[Dict]:
    """Helper function that takes care of extracting the DB data and convert it
    into JSON data.

    Args:
        db (Session): DB Session to use for calling the DB.
        db_table_id (int): ID of the Table from which to extract the data.
        parameters (Parameters): Parameters for filtering/grouping/etc... the
            data to be extracted from the DB.

    Raises:
        TooMuchAttributes: Exception raised if the number of attributes to
            return is bigger than the limit (MAX_ATTRIBUTES).

    Returns:
        List[Dict]: JSON data corresponding to this table.
    """
    db_attributes = crud.get_attributes_of_table(
        db, db_table_id, calculate=parameters.calculate, limit=MAX_ATTRIBUTES + 1
    )

    # If there is too much data, raise an exception so the server can properly inform the client
    if len(db_attributes) > MAX_ATTRIBUTES:
        raise TooMuchAttributes()

    data = defaultdict(lambda: {})
    for attr in db_attributes:
        if attr.is_bool:
            value = attr.value_bool
        elif attr.is_date:
            value = attr.value_date
        elif attr.is_number:
            value = attr.value_number
        elif attr.is_string:
            value = attr.value_string
        elif attr.is_multistring:
            value = json.loads(attr.value_string)

        data[attr.element_id][attr.name] = value

    return list(data.values())


def get_data(db: Session, table: models.Table, parameters: Parameters) -> List[Dict]:
    """Retrieve the data for this table.

    The data is cached on the DB for fast retrieval and custom queries and
    filters.
    When this function is called, we call the Notion API to get only the latest
    changes that are not in the cache yet. If the cache is up-to-date, fine !
    And we return the data retrieved.

    Args:
        db (Session): DB Session to use for calling the DB.
        table (models.Table): Table for which we should retrieve the data.
        parameters (Parameters): Parameters for filtering/grouping/etc... the
            data extracted from the DB.

    Returns:
        List[Dict]: Data from the Notion table.
    """
    if parameters.reset_cache:
        crud.delete_elements_of_table(db, table.id)
        parameters.update_cache = True

    if parameters.update_cache:
        # Get the latest element to know from which date to retrieve stuff
        db_latest_element = crud.last_table_element(db, table.id) if not parameters.reset_cache else None

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

    return extract_data_from_db(db, table.id, parameters)


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
        schema = {name: prop["type"] for name, prop in notion_db["properties"].items()}
    else:
        # We have some data, use this to create the schema
        schema = {attr.name: attr.type for attr in db_latest_element.attributes}

    # Clothion doesn't support `rollup` or `relation` attributes, remove them
    return {name: attr_type for name, attr_type in schema.items() if attr_type not in ["relation", "rollup"]}
