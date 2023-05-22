import uuid
from typing import Callable, Dict

from dateutil.parser import isoparse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from clothion.database import engine, models


KEY_NAME = {
    "people": "id",
    "files": "name",
    "multi_select": "name",
}


def create_tables():
    models.Base.metadata.create_all(bind=engine)


def get_integration(db: Session, id: int):
    return db.query(models.Integration).filter(models.Integration.id == id).first()


def get_integration_by_token(db: Session, token: str):
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


def create_integration(db: Session, token: str):
    # Create a random ID that doesn't exist on the table yet
    random_id = generate_random_unique_id(lambda i: get_integration(db=db, id=i) is None)

    db_integration = models.Integration(id=random_id, token=token)
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration


def get_table_by_table_id(db: Session, integration_id: int, table_id: str):
    return (
        db.query(models.Table)
        .filter(models.Table.integration_id == integration_id)
        .filter(models.Table.table_id == table_id)
        .first()
    )


def get_table(db: Session, integration_id: int, id: int):
    return (
        db.query(models.Table)
        .filter(models.Table.integration_id == integration_id)
        .filter(models.Table.id == id)
        .first()
    )


def create_table(db: Session, integration_id: int, table_id: str):
    # Create a random ID that doesn't exist on the table yet
    random_id = generate_random_unique_id(lambda i: get_table(db=db, integration_id=integration_id, id=i) is None)

    db_table = models.Table(id=random_id, table_id=table_id, integration_id=integration_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table


def last_table_element(db: Session, table_id: int):
    return (
        db.query(models.Element)
        .filter(models.Element.table_id == table_id)
        .order_by(models.Element.last_edited.desc())
        .first()
    )


def delete_elements_of_table(db: Session, table_id: id):
    db.query(models.Element).filter(models.Element.table_id == table_id).delete()
    db.commit()


def get_element_by_notion_id(db: Session, notion_id: str):
    return db.query(models.Element).filter(models.Element.notion_id == notion_id).first()


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
        kwargs["value_string"] = "".join(t["plain_text"] for t in attr["title"])
        kwargs["is_string"] = True
    elif attr["type"] == "checkbox":
        kwargs["value_bool"] = attr["checkbox"]
        kwargs["is_bool"] = True
    elif attr["type"] == "rich_text":
        kwargs["value_string"] = "".join(t["plain_text"] for t in attr["rich_text"])
        kwargs["is_string"] = True
    elif attr["type"] == "string":
        kwargs["value_string"] = attr["string"]
        kwargs["is_string"] = True
    elif attr["type"] == "number":
        kwargs["value_number"] = attr["number"]
        kwargs["is_number"] = True
    elif attr["type"] == "select":
        kwargs["value_string"] = attr["select"]["name"] if attr["select"] else ""
        kwargs["is_string"] = True
    elif attr["type"] == "multi_select" or attr["type"] == "people" or attr["type"] == "files":
        # Special case, the values will be contained in another table !
        kwargs["is_multistring"] = True
    elif attr["type"] == "status":
        kwargs["value_string"] = attr["status"]["name"]
        kwargs["is_string"] = True
    elif attr["type"] == "date":
        kwargs["value_date"] = isoparse(attr["date"]["start"]) if attr["date"] else None
        kwargs["is_date"] = True
    elif attr["type"] == "url":
        kwargs["value_string"] = attr["url"] if attr["url"] else ""
        kwargs["is_string"] = True
    elif attr["type"] == "email":
        kwargs["value_string"] = attr["email"] if attr["email"] else ""
        kwargs["is_string"] = True
    elif attr["type"] == "phone_number":
        kwargs["value_string"] = attr["phone_number"] if attr["phone_number"] else ""
        kwargs["is_string"] = True
    elif attr["type"] == "formula":
        # Formula is special, the underlying data can be any type !
        return notion_attr_to_db_attr(name, attr["formula"], element_id, "formula")
    elif attr["type"] == "relation" or attr["type"] == "rollup":
        # Types that can't be handled by our DB
        return None
    elif attr["type"] == "created_time":
        kwargs["value_date"] = isoparse(attr["created_time"])
        kwargs["is_date"] = True
    elif attr["type"] == "created_by":
        kwargs["value_string"] = attr["created_by"]["id"]
        kwargs["is_string"] = True
    elif attr["type"] == "last_edited_time":
        kwargs["value_date"] = isoparse(attr["last_edited_time"])
        kwargs["is_date"] = True
    elif attr["type"] == "last_edited_by":
        kwargs["value_string"] = attr["last_edited_by"]["id"]
        kwargs["is_string"] = True

    return models.Attribute(**kwargs)


def create_attribute(db: Session, name: str, attr: Dict, element_id: int):
    db_attr = notion_attr_to_db_attr(name, attr, element_id)

    if db_attr is None:
        return

    db.add(db_attr)
    db.commit()

    # Special case, for attributes with multiple values, we need to add the
    # values in a different table as well !
    t = attr["type"]
    if t == "files" or t == "multi_select" or t == "people":
        db.refresh(db_attr)

        for value in attr[t]:
            db_attr_part = models.StringPart(text=value[KEY_NAME[t]], attribute_id=db_attr.id)
            db.add(db_attr_part)

        db.commit()


def create_element(db: Session, notion_id: str, table_id: int, last_edited: str, attributes: Dict):
    # First, create the element
    db_element = models.Element(table_id=table_id, notion_id=notion_id, last_edited=isoparse(last_edited))
    db.add(db_element)
    db.commit()
    db.refresh(db_element)

    # Then, create each attribute of the element
    for name, attr in attributes.items():
        create_attribute(db, name, attr, db_element.id)

    db.refresh(db_element)
    return db_element


def update_element(db: Session, db_element: models.Element, last_edited: str, attributes: Dict):
    # Update the element itself
    db_element.last_edited = isoparse(last_edited)
    db.commit()

    # Delete all of its previous attribute
    db.query(models.Attribute).filter(models.Attribute.element_id == db_element.id).delete()

    # Recreate the attributes from the updated values
    for name, attr in attributes.items():
        create_attribute(db, name, attr, db_element.id)

    db.refresh(db_element)
    return db_element


def get_multistring(db: Session, attribute_id: int):
    return db.query(models.StringPart).filter(models.StringPart.attribute_id == attribute_id).all()


def get_attributes_of_table(db: Session, table_id: int, calculate: str = None, limit: int = 500):
    if calculate == "sum":
        query = (
            db.query(
                models.Attribute.element_id,
                models.Attribute.id,
                models.Attribute.name,
                models.Attribute.value_bool,
                models.Attribute.value_date,
                func.sum(models.Attribute.value_number).label("value_number"),
                models.Attribute.value_string,
                models.Attribute.is_bool,
                models.Attribute.is_date,
                models.Attribute.is_number,
                models.Attribute.is_string,
                models.Attribute.is_multistring,
            )
            .filter(models.Attribute.is_number)
            .group_by(models.Attribute.name)
        )
    else:
        query = db.query(
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

    # Get only the attributes for the elements of the given table
    query = query.join(models.Element).filter(models.Element.table_id == table_id)

    # Limit the size of the query and return the results
    return query.limit(limit).all()
