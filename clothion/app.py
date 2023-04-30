from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from clothion import __version__, config
from clothion.database import SessionLocal, crud, schemas


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/version", tags=["API"])
async def version() -> str:
    return __version__


@app.post("/integration", response_model=schemas.Integration)
def create_integration(integration: schemas.IntegrationCreate, db: Session = Depends(get_db)):
    db_integration = crud.get_integration_by_token(db, token=integration.token)
    if not db_integration:
        db_integration = crud.create_integration(db=db, integration=integration)
    return db_integration


@app.get("/{integration_id}", response_model=schemas.Integration)
def read_integration(integration_id: int, db: Session = Depends(get_db)):
    db_integration = crud.get_integration(db, id=integration_id)
    if db_integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return db_integration


@app.post("/{integration_id}/table", response_model=schemas.Table)
def create_table_for_integration(integration_id: int, table: schemas.TableCreate, db: Session = Depends(get_db)):
    return crud.create_table(db=db, table=table, integration_id=integration_id)


@app.get("/{integration_id}/tables", response_model=List[schemas.Table])
def read_tables(integration_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tables = crud.get_tables_of(db, integration_id=integration_id, skip=skip, limit=limit)
    return tables


def serve():
    if config.db == "local":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
