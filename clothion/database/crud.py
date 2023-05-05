import uuid
from typing import Callable

from sqlalchemy.orm import Session

from clothion.database import engine, models


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


def get_tables_of(db: Session, integration_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Table).filter(models.Table.integration_id == integration_id).offset(skip).limit(limit).all()


def create_table(db: Session, integration_id: int, table_id: str):
    # Create a random ID that doesn't exist on the table yet
    random_id = generate_random_unique_id(lambda i: get_table(db=db, integration_id=integration_id, id=i) is None)

    db_table = models.Table(id=random_id, table_id=table_id, integration_id=integration_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table
