from sqlalchemy.orm import Session

from clothion.database import engine, models, schemas


def create_tables():
    print("creating tables...")
    models.Base.metadata.create_all(bind=engine)


def get_integration(db: Session, id: int):
    return db.query(models.Integration).filter(models.Integration.id == id).first()


def get_integration_by_token(db: Session, token: str):
    return db.query(models.Integration).filter(models.Integration.token == token).first()


def create_integration(db: Session, integration: schemas.IntegrationCreate):
    db_integration = models.Integration(token=integration.token)
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    return db_integration


def get_tables_of(db: Session, integration_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Table).filter(models.Table.integration_id == integration_id).offset(skip).limit(limit).all()


def create_table(db: Session, table: schemas.TableCreate, integration_id: int):
    db_table = models.Table(**table.dict(), integration_id=integration_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table
