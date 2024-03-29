"""CRUD functions to interact with the DB."""

import json
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Union

from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, case, not_, or_, sql
from sqlalchemy.orm import Session
from sqlalchemy.orm.query import Query
from sqlalchemy.sql import func

from clothion.database import engine, models


KEY_NAME = {
    "people": "id",
    "files": "name",
    "multi_select": "name",
}
NUMBER_OP = {
    "sum": func.sum,
    "min": func.min,
    "max": func.max,
    "average": func.avg,
}
BOOL = "boolean"
DATE = "date"
NUMBER = "number"
STRING = "string"
MULTISTRING = "multistring"


class WrongFilter(Exception):
    """Custom exception raised when the filters provided by the user are
    invalid.
    """

    pass


def create_tables():
    """Util function to create the DB tables.

    Warning, this function should be called only if the DB tables aren't
    already created.
    """
    models.Base.metadata.create_all(bind=engine)


def get_integration(db: Session, id: int) -> models.Integration:
    """CRUD function to retrieve the integration their ID.

    Args:
        db (Session): DB Session.
        id (int): ID of the integration to retrieve.

    Returns:
        models.Integration: Queried Integration.
    """
    return db.query(models.Integration).filter(models.Integration.id == id).first()


def get_integration_by_token(db: Session, token: str) -> models.Integration:
    """CRUD function to retrieve the integration their token.

    Args:
        db (Session): DB Session.
        token (str): Token of the integration to retrieve.

    Returns:
        models.Integration: Queried Integration.
    """
    return db.query(models.Integration).filter(models.Integration.token == token).first()


def generate_random_id() -> int:
    """Util function to generate a random int that fits in DB and can be used
    as ID.

    Returns:
        int: Randomly generated int.
    """
    random_id = uuid.uuid4().int

    # The generated ID is 128 bits, but in DB an INTEGER is at most 4 bytes
    # (32 bits), so reduce it to the right number of bytes
    return random_id >> (128 - 32)


def generate_random_unique_id(uniq_fn: Callable[int, bool]) -> int:
    """Util function to generate a random, unique int that fits in DB and can
    be used as ID. The given function is used to ensure the generated int is
    unique.

    Args:
        uniq_fn (Callable[int, bool]): Function that can be used to check if
            a int is already is use or not.

    Returns:
        int: Randomly generated, unique int.
    """
    random_id = generate_random_id()
    while not uniq_fn(random_id):
        random_id = generate_random_id()
    return random_id


def create_integration(db: Session, token: str) -> models.Integration:
    """CRUD function to create a new Integration.

    Args:
        db (Session): DB Session.
        token (str): Integration token to register.

    Returns:
        models.Integration: Created Integration.
    """
    # Create a random ID that doesn't exist on the table yet
    random_id = generate_random_unique_id(lambda i: get_integration(db=db, id=i) is None)

    db_integration = models.Integration(id=random_id, token=token)
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration


def get_table_by_table_id(db: Session, integration_id: int, table_id: str) -> models.Table:
    """CRUD function to retrieve the table their Notion table ID.

    Args:
        db (Session): DB Session.
        integration_id (int): ID of the table's integration.
        table_id (str): Notion table ID of the table to retrieve.

    Returns:
        models.Table: Queried Table.
    """
    return (
        db.query(models.Table)
        .filter(models.Table.integration_id == integration_id)
        .filter(models.Table.table_id == table_id)
        .first()
    )


def get_table(db: Session, integration_id: int, id: int) -> models.Table:
    """CRUD function to retrieve a table by their ID.

    Args:
        db (Session): DB Session.
        integration_id (int): ID of the table's integration.
        id (int): ID of the table to retrieve.

    Returns:
        models.Table: Queried Table.
    """
    return (
        db.query(models.Table)
        .filter(models.Table.integration_id == integration_id)
        .filter(models.Table.id == id)
        .first()
    )


def create_table(db: Session, integration_id: int, table_id: str) -> models.Table:
    """CRUD function to create a new Table.

    Args:
        db (Session): DB Session.
        integration_id (int): ID of the table's integration.
        table_id (str): Notion table ID of the table.

    Returns:
        models.Table: Created Table.
    """
    # Create a random ID that doesn't exist on the table yet
    random_id = generate_random_unique_id(lambda i: get_table(db=db, integration_id=integration_id, id=i) is None)

    db_table = models.Table(id=random_id, table_id=table_id, integration_id=integration_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table


def last_table_element(db: Session, table_id: int) -> models.Element:
    """CRUD function to get the last Element of a Table.

    Args:
        db (Session): DB Session.
        table_id (str): ID of the table.

    Returns:
        models.Element: Last Element of the Table.
    """
    return (
        db.query(models.Element)
        .filter(models.Element.table_id == table_id)
        .order_by(models.Element.last_edited.desc())
        .first()
    )


def delete_elements_of_table(db: Session, table_id: id):
    """CRUD function to delete all elements of a Table.

    Args:
        db (Session): DB Session.
        table_id (str): ID of the table.
    """
    db.query(models.Element).filter(models.Element.table_id == table_id).delete()
    db.commit()


def get_element_by_notion_id(db: Session, notion_id: str) -> models.Element:
    """CRUD function to get the Element with a given Notion ID.

    Args:
        db (Session): DB Session.
        notion_id (str): Notion ID of the element to retrieve.

    Returns:
        models.Element: Element with the given Notion ID.
    """
    return db.query(models.Element).filter(models.Element.notion_id == notion_id).first()


def parse_date(d: str) -> datetime:
    """Small util function parsing a ISO-8601 date string into a datetime
    object, removing the timezone if any.

    Args:
        d (str): ISO-8601 date string to parse.

    Returns:
        datetime: Date parsed.
    """
    date = isoparse(d)

    if date.tzinfo is not None:
        date = date.astimezone(timezone.utc)

    return date


def notion_attr_to_db_attr(name: str, attr: Dict, element_id: int, attr_type: str = None) -> models.Base:  # noqa: C901
    """Helper function converting an attribute coming from the Notion API into
    a DB row corresponding to the right type.

    Args:
        name (str): Name of the attribute.
        attr (Dict): Content of the attribute (from Notion API).
        element_id (int): ID of the element this attribute belongs to (for
            linking).
        attr_type (str): Type of this attribute. If `None`, uses the type as
            described in the attribute's content. Defaults to `None`.

    Returns:
        models.Base: The DB row to add.
    """
    if attr_type is None:
        attr_type = attr["type"]

    kwargs = {"name": name, "type": attr_type, "element_id": element_id}

    if attr["type"] == "title":
        if attr["title"]:
            kwargs["value_string"] = "".join(t["plain_text"] for t in attr["title"])
        kwargs["is_string"] = True
    elif attr["type"] == "checkbox":
        kwargs["value_bool"] = attr["checkbox"]
        kwargs["is_bool"] = True
    elif attr["type"] == "rich_text":
        if attr["rich_text"]:
            kwargs["value_string"] = "".join(t["plain_text"] for t in attr["rich_text"])
        kwargs["is_string"] = True
    elif attr["type"] == "string":
        kwargs["value_string"] = attr["string"]
        kwargs["is_string"] = True
    elif attr["type"] == "number":
        kwargs["value_number"] = attr["number"]
        kwargs["is_number"] = True
    elif attr["type"] == "select":
        if attr["select"]:
            kwargs["value_string"] = attr["select"]["name"]
        kwargs["is_string"] = True
    elif attr["type"] == "multi_select":
        if attr["multi_select"]:
            kwargs["value_string"] = json.dumps([x["name"] for x in attr["multi_select"]])
        kwargs["is_multistring"] = True
    elif attr["type"] == "people":
        if attr["people"]:
            kwargs["value_string"] = json.dumps([x["id"] for x in attr["people"]])
        kwargs["is_multistring"] = True
    elif attr["type"] == "files":
        if attr["files"]:
            kwargs["value_string"] = json.dumps([x["name"] for x in attr["files"]])
        kwargs["is_multistring"] = True
    elif attr["type"] == "status":
        kwargs["value_string"] = attr["status"]["name"]
        kwargs["is_string"] = True
    elif attr["type"] == "date":
        if attr["date"]:
            kwargs["value_date"] = parse_date(attr["date"]["start"])
        kwargs["is_date"] = True
    elif attr["type"] == "url":
        if attr["url"]:
            kwargs["value_string"] = attr["url"]
        kwargs["is_string"] = True
    elif attr["type"] == "email":
        if attr["email"]:
            kwargs["value_string"] = attr["email"]
        kwargs["is_string"] = True
    elif attr["type"] == "phone_number":
        if attr["phone_number"]:
            kwargs["value_string"] = attr["phone_number"]
        kwargs["is_string"] = True
    elif attr["type"] == "formula":
        # Formula is special, the underlying data can be any type !
        return notion_attr_to_db_attr(name, attr["formula"], element_id, "formula")
    elif attr["type"] == "relation" or attr["type"] == "rollup":
        # Types that can't be handled by our DB
        return None
    elif attr["type"] == "created_time":
        kwargs["value_date"] = parse_date(attr["created_time"])
        kwargs["is_date"] = True
    elif attr["type"] == "created_by":
        kwargs["value_string"] = attr["created_by"]["id"]
        kwargs["is_string"] = True
    elif attr["type"] == "last_edited_time":
        kwargs["value_date"] = parse_date(attr["last_edited_time"])
        kwargs["is_date"] = True
    elif attr["type"] == "last_edited_by":
        kwargs["value_string"] = attr["last_edited_by"]["id"]
        kwargs["is_string"] = True

    return models.Attribute(**kwargs)


def create_attribute(db: Session, name: str, attr: Dict, element_id: int):
    """CRUD function to create the given Attribute in DB.

    Args:
        db (Session): DB Session.
        name (str): Name of the attribute.
        attr (Dict): Data of the attribute (from Notion API), to be parsed.
        element_id (int): ID of the element this attribute belongs to.
    """
    db_attr = notion_attr_to_db_attr(name, attr, element_id)

    if db_attr is None:
        return

    db.add(db_attr)
    db.commit()


def create_element(db: Session, notion_id: str, table_id: int, last_edited: str, attributes: Dict) -> models.Element:
    """CRUD function to create an element, with all its attributes.

    Args:
        db (Session): DB Session.
        notion_id (str): Notion ID of the element.
        table_id (int): ID of the table this element belongs to.
        last_edited (str): ISO-8601 date string representing when this element
            was last edited.
        attributes (Dict): Dictionary of all attributes of this element.

    Returns:
        models.Element: Element created.
    """
    # First, create the element
    db_element = models.Element(
        table_id=table_id, notion_id=notion_id, last_edited=isoparse(last_edited).astimezone(timezone.utc)
    )
    db.add(db_element)
    db.commit()
    db.refresh(db_element)

    # Then, create each attribute of the element
    for name, attr in attributes.items():
        create_attribute(db, name, attr, db_element.id)

    db.refresh(db_element)
    return db_element


def update_element(db: Session, db_element: models.Element, last_edited: str, attributes: Dict) -> models.Element:
    """CRUD function to update an element, with all its attributes.

    This will simply update the `last_edited` field, and then delete all
    associated attributes, and recreate them from the given attribute list.

    Args:
        db (Session): DB Session.
        db_element (models.Element): Element to update.
        last_edited (str): ISO-8601 date string representing when this element
            was last edited.
        attributes (Dict): Dictionary of all attributes of this element.

    Returns:
        models.Element: Element updated.
    """
    # Update the element itself
    db_element.last_edited = isoparse(last_edited).astimezone(timezone.utc)
    db.commit()

    # Delete all of its previous attribute
    db.query(models.Attribute).filter(models.Attribute.element_id == db_element.id).delete()

    # Recreate the attributes from the updated values
    for name, attr in attributes.items():
        create_attribute(db, name, attr, db_element.id)

    db.refresh(db_element)
    return db_element


def make_condition(  # noqa: C901
    prop: models.Base, op: str, value: Union[bool, str, float, int], prop_type: str
) -> sql.elements.BinaryExpression:
    """Function creating the DB condition for a given operator.

    Args:
        prop (models.Base): The model property to use for the condition.
        op (str): The condition operation specified by the user.
        value (Union[bool, str, float, int]): The value specified by the user.
        prop_type (str): The type of the property (the value specified by the
            user should match this type).

    Raises:
        WrongFilter: Exception thrown when the filter descriptor is not valid.

    Returns:
        sql.elements.BinaryExpression: DB condition that can be used to create
            a bigger filter together with other operations.
    """
    # Assign the expected type dependending on the property's type
    if prop_type == BOOL:
        expected_types = (bool,)
    elif prop_type == NUMBER:
        expected_types = (int, float)
    elif prop_type == STRING:
        expected_types = (str,)
    elif prop_type == DATE:
        expected_types = (datetime,)
        if op not in ["is_empty", "past", "next", "this"]:
            # Other operations than these should have a datetime string as value
            try:
                if not isinstance(value, str):
                    raise ValueError
                value = isoparse(value).astimezone(timezone.utc)
            except ValueError:
                raise WrongFilter(f"Given value for date ({value}) is not a valid date)")
    elif prop_type == MULTISTRING:
        expected_types = (str,)
        if op != "is_empty":
            # Inside the DB, the values are stored as JSON, so we need to encode the
            # given value properly so that `contains` and `does_not_contain` works properly
            if not isinstance(value, str):
                raise WrongFilter(f"Filter `{op}` expected a value of type {expected_types} (but got {type(value)})")
            value = json.dumps(value)

    if op == "is" or op == "is_not":
        # Parameters / types validation
        if prop_type == MULTISTRING:
            raise WrongFilter(
                f"Multi-string attribute can't use `{op}` filters. Use `contains`/`does_not_contain` instead"
            )
        if type(value) not in expected_types:
            raise WrongFilter(f"Filter `{op}` expected a value of type {expected_types} (but got {type(value)})")

        # Actual comparison
        if op == "is":
            return prop == value
        elif op == "is_not":
            return prop != value
    elif op == "is_empty":
        # Parameters / types validation
        if prop_type == BOOL:
            raise WrongFilter(f"Boolean attribute can never be empty. Can't use `{op}` filter.")
        if not isinstance(value, bool):
            raise WrongFilter(f"Filter `{op}` expected a value of type boolean (but got {type(value)})")

        # Actual condition
        if value is True:
            return prop.is_(None)
        else:
            return prop.is_not(None)
    elif op in ["after", "on_or_after", "before", "on_or_before", "past", "next", "this"]:
        # Parameters / types validation
        if prop_type != DATE:
            raise WrongFilter(f"Filter `{op}` can only be applied to Date attributes.")

        # Actual conditions
        if op == "after":
            return prop > value
        elif op == "on_or_after":
            return prop >= value
        elif op == "before":
            return prop < value
        elif op == "on_or_before":
            return prop <= value
        elif op == "past" or op == "next":
            if value == "week":
                delta = relativedelta(weeks=1)
            elif value == "month":
                delta = relativedelta(months=1)
            elif value == "year":
                delta = relativedelta(years=1)
            else:
                raise WrongFilter(f"Unknown time window `{value}`. Please use `week`, `month` or `year`.")

            now = datetime.now(timezone.utc)
            if op == "past":
                return prop.between(now - delta, now)
            elif op == "next":
                return prop.between(now, now + delta)
        elif op == "this":
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            if value == "week":
                start = today - relativedelta(days=today.weekday())
                delta = relativedelta(weeks=1)
            elif value == "month":
                start = today.replace(day=1)
                delta = relativedelta(months=1)
            elif value == "year":
                start = today.replace(month=1, day=1)
                delta = relativedelta(years=1)
            else:
                raise WrongFilter(f"Unknown time window `{value}`. Please use `week`, `month` or `year`.")
            return prop.between(start, start + delta)
    elif op in ["greater_than", "less_than", "greater_or_equal", "less_or_equal"]:
        # Parameters / types validation
        if prop_type != NUMBER:
            raise WrongFilter(f"Filter `{op}` can only be applied to number attributes.")
        if type(value) not in expected_types:
            raise WrongFilter(f"Filter `{op}` expected a value of type {expected_types} (but got {type(value)})")

        # Actual condition
        if op == "greater_than":
            return prop > value
        elif op == "greater_or_equal":
            return prop >= value
        elif op == "less_than":
            return prop < value
        elif op == "less_or_equal":
            return prop <= value
    elif op in ["starts_with", "ends_with"]:
        # Parameters / types validation
        if prop_type != STRING:
            raise WrongFilter(f"Filter `{op}` can only be applied to string attributes.")
        if type(value) not in expected_types:
            raise WrongFilter(f"Filter `{op}` expected a value of type {expected_types} (but got {type(value)})")

        # Actual condition
        if op == "starts_with":
            return prop.startswith(value)
        elif op == "ends_with":
            return prop.endswith(value)
    elif op in ["contains", "does_not_contain"]:
        # Parameters / types validation
        if prop_type != STRING and prop_type != MULTISTRING:
            raise WrongFilter(f"Filter `{op}` can only be applied to string or multi-strings attributes.")
        if type(value) not in expected_types:
            raise WrongFilter(f"Filter `{op}` expected a value of type {expected_types} (but got {type(value)})")

        # Actual condition
        if op == "contains":
            return prop.contains(value)
        elif op == "does_not_contain":
            return not_(prop.contains(value))
    elif op == "contains_only":
        # Parameters / types validation
        if prop_type != MULTISTRING:
            raise WrongFilter(f"Filter `{op}` can only be applied to multi-strings attributes.")
        # No need to check that value is a `str`, since we know it's a multistring it was parsed earlier

        # Actual condition
        # If it contains only the given value, then represent the value as a list and check for equality !
        return prop == f"[{value}]"
    else:
        raise WrongFilter(f"Unknown filter condition ({op})")


def create_db_filter(  # noqa: C901
    db: Session,
    table_id: int,
    filter: Dict[str, Dict] = None,
    db_element: models.Base = None,
) -> sql.selectable.Exists:
    """Take a filter descriptor (the thing sent by the user in his request) and
    turn it into a DB filter that can be used in the query to properly filter
    the elements to return.

    Args:
        db (Session): DB Session to use for calling the DB.
        table_id (int): ID of the Table from which to extract the data.
        filter (Dict[str, Dict], optional): Filter descriptor sent by the user.
            Defaults to None.
        db_element (models.Base): If specified, one element from the DB for the
            corresponding table (to avoid re-calling the DB to retrieve this
            element). Just used when this function is called recursively.

    Raises:
        WrongFilter: Exception thrown when the filter descriptor is not valid.

    Returns:
        sql.selectable.Exists: DB filter that can be applied with `filter`
            method in `sqlalchemy`.
    """
    # We will gather the filters on each attribute here
    db_elem_conditions = []

    # No filter, or if the table is empty, nothing to filter
    db_element = last_table_element(db, table_id) if db_element is None else db_element
    if filter is None or db_element is None:
        return None

    # OR filter can only be at the root of the filter field
    # Just create the filters for each clause and merge them with OR
    if "or" in filter and isinstance(filter["or"], list):
        filters = [
            create_db_filter(db=db, table_id=table_id, filter=clause, db_element=db_element) for clause in filter["or"]
        ]
        return or_(*filters)

    # First, we need the schema for validating the filter
    db_attributes = {attr.name: attr for attr in db_element.attributes}

    # Filter are applied on each attribute
    for attr_name, attr_filter in filter.items():
        if attr_name not in db_attributes:
            raise WrongFilter(f"Unknown attribute ({attr_name})")
        if isinstance(attr_filter, list):
            raise WrongFilter(
                f"Received a list instead of a dict for {attr_name}. Only `or` filter can be a list, you should use "
                "a dict for individual filters."
            )

        # Always the first condition is to get the right attribute (identified by its name)
        db_attr_conditions = [models.Attribute.name == attr_name]

        # Then, add all conditions defined in the query
        if db_attributes[attr_name].is_bool:
            for op, value in attr_filter.items():
                db_attr_conditions.append(make_condition(models.Attribute.value_bool, op, value, BOOL))
        elif db_attributes[attr_name].is_number:
            for op, value in attr_filter.items():
                db_attr_conditions.append(make_condition(models.Attribute.value_number, op, value, NUMBER))
        elif db_attributes[attr_name].is_string:
            for op, value in attr_filter.items():
                db_attr_conditions.append(make_condition(models.Attribute.value_string, op, value, STRING))
        elif db_attributes[attr_name].is_date:
            for op, value in attr_filter.items():
                db_attr_conditions.append(make_condition(models.Attribute.value_date, op, value, DATE))
        elif db_attributes[attr_name].is_multistring:
            for op, value in attr_filter.items():
                db_attr_conditions.append(make_condition(models.Attribute.value_string, op, value, MULTISTRING))

        # Gather the conditions for this attribute
        db_attr_condition = and_(*db_attr_conditions)

        # And find elements that have such attribute
        db_elem_conditions.append(models.Element.attributes.any(db_attr_condition))

    return and_(*db_elem_conditions)


def create_base_db_query(db: Session, table_id: int, calculate: str = None, group_by: str = None) -> Query:
    """Take a calculate descriptor and a group_by descriptor (the argument sent
    by the user in his request) and turn it into a DB query that will retrieve
    the right results.

    Args:
        db (Session): DB Session to use for calling the DB.
        table_id (int): ID of the Table from which to extract the data.
        calculate (str): Descriptor sent by the user specifying which
            aggregation function to use. Defaults to None.
        group_by (str): Descriptor sent by the user specifying by which
            attribute to group by results. Defaults to None.

    Raises:
        WrongFilter: Exception thrown when the descriptors are not valid.

    Returns:
        Query: The DB query to use.
    """
    if group_by is None and calculate is None:
        # Nothing to do, return a query to retrieve all elements
        return db.query(
            models.Attribute.element_id,
            models.Attribute.id,
            models.Attribute.name,
            models.Attribute.value_bool,
            models.Attribute.value_date,
            models.Attribute.value_number,
            models.Attribute.value_string,
            models.Attribute.is_bool,
            models.Attribute.is_date,
            models.Attribute.is_number,
            models.Attribute.is_string,
            models.Attribute.is_multistring,
        )

    if group_by is not None and calculate is None:
        raise WrongFilter("Can't group_by if not aggregation function is given through `calculate`")

    # Create a subquery for grouping by the right thing
    if group_by is not None:
        grouper = (
            db.query(
                models.Attribute.element_id,
                case(
                    (models.Attribute.is_bool, models.Attribute.value_bool),
                    (models.Attribute.is_date, models.Attribute.value_date),
                    (models.Attribute.is_number, models.Attribute.value_number),
                    (models.Attribute.is_string, models.Attribute.value_string),
                    (models.Attribute.is_multistring, models.Attribute.value_string),
                ).label("group_id"),
            )
            .join(models.Element)
            .filter(models.Element.table_id == table_id, models.Attribute.name == group_by)
            .subquery()
        )
    else:
        grouper = (
            db.query(models.Attribute.element_id, models.Element.table_id.label("group_id"))
            .join(models.Element)
            .filter(models.Element.table_id == table_id)
            .group_by(models.Attribute.element_id)
            .subquery()
        )

    if calculate in ["sum", "min", "max", "average"]:
        fn = NUMBER_OP[calculate]
        return (
            db.query(
                grouper.c.group_id.label("element_id"),
                models.Attribute.name,
                case(
                    (func.count(models.Attribute.value_bool.distinct()) == 1, models.Attribute.value_bool), else_=None
                ).label("value_bool"),
                case(
                    (func.count(models.Attribute.value_date.distinct()) == 1, models.Attribute.value_date), else_=None
                ).label("value_date"),
                fn(models.Attribute.value_number).label("value_number"),
                case(
                    (func.count(models.Attribute.value_string.distinct()) == 1, models.Attribute.value_string),
                    else_=None,
                ).label("value_string"),
                models.Attribute.is_bool,
                models.Attribute.is_date,
                models.Attribute.is_number,
                models.Attribute.is_string,
                models.Attribute.is_multistring,
            )
            .join(grouper, models.Attribute.element_id == grouper.c.element_id)
            .group_by(models.Attribute.name, grouper.c.group_id)
        )
    elif calculate in ["count", "count_unique"]:
        if calculate == "count":
            value_bool = models.Attribute.value_bool
            value_date = models.Attribute.value_date
            value_number = models.Attribute.value_number
            value_string = models.Attribute.value_string
        elif calculate == "count_unique":
            value_bool = models.Attribute.value_bool.distinct()
            value_date = models.Attribute.value_date.distinct()
            value_number = models.Attribute.value_number.distinct()
            value_string = models.Attribute.value_string.distinct()

        return (
            db.query(
                grouper.c.group_id.label("element_id"),
                models.Attribute.name,
                func.count(value_bool).label("value_bool"),
                func.count(value_date).label("value_date"),
                func.count(value_number).label("value_number"),
                func.count(value_string).label("value_string"),
                models.Attribute.is_bool,
                models.Attribute.is_date,
                models.Attribute.is_number,
                models.Attribute.is_string,
                models.Attribute.is_multistring,
            )
            .join(grouper, models.Attribute.element_id == grouper.c.element_id)
            .group_by(models.Attribute.name, grouper.c.group_id)
        )
    else:
        raise WrongFilter(f"Unknown calculate function : {calculate}")


def get_attributes_of_table(
    db: Session,
    table_id: int,
    calculate: str = None,
    filter: Dict[str, Dict] = None,
    group_by: str = None,
    limit: int = 500,
) -> models.Attribute:
    """Main CRUD function, retrieving the data queried by the user.

    Args:
        db (Session): DB Session.
        table_id (int): ID of the queried Table.
        calculate (str, optional): Function to apply to gather the data.
            Defaults to `None`.
        filter (Dict[str, Dict], optional): Filters to apply to the data.
            Defaults to `None`.
        group_by (str, optional): Grouping the data by this attribtute.
            Defaults to `None`.
        limit (int, optional): Maximum number of results to return. Defaults
            to `500`.

    Returns:
        models.Attribute: All attributes corresponding to this query.
    """
    # Query the right thing (based on calculate & group_by)
    query = create_base_db_query(db=db, table_id=table_id, calculate=calculate, group_by=group_by)

    # Create optional filters
    db_filter = create_db_filter(db, table_id, filter)
    filter_args = [db_filter] if db_filter is not None else []

    # Get only the attributes for the right elements
    query = query.join(models.Element).filter(models.Element.table_id == table_id, *filter_args)

    # Limit the size of the query and return the results
    return query.limit(limit).all()
