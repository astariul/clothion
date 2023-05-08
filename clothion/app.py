import binascii
import pathlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
from sqlalchemy.orm import Session

from clothion import __version__, config
from clothion.database import SessionLocal, crud


N_BYTES = 4
ENDIAN = "big"


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)

templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PageNotFound(Exception):
    pass


@app.exception_handler(PageNotFound)
async def http_exception_handler(request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)


@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(pathlib.Path(__file__).parent / "templates" / "logo.svg")


@app.get("/version", tags=["API"])
async def version() -> str:
    return __version__


@app.post("/create")
def create(integration: Annotated[str, Form()], table: Annotated[str, Form()], db: Session = Depends(get_db)):
    db_integration = crud.get_integration_by_token(db, token=integration)
    if not db_integration:
        # If the Integration doesn't exist, create it and create the table directly
        # because if there was no integration, there was no table !
        db_integration = crud.create_integration(db=db, token=integration)
        db_table = crud.create_table(db=db, integration_id=db_integration.id, table_id=table)
    else:
        # If the Integration exists, we have to check if the table already exists or not
        db_table = crud.get_table_by_table_id(db, integration_id=db_integration.id, table_id=table)
        if not db_table:
            db_table = crud.create_table(db=db, integration_id=db_integration.id, table_id=table)

    # To have smaller URL, encode the IDs in base64
    # Because our ID are on 4 bytes, we can remove the base64 padding ("==") at the end
    integration_b64 = urlsafe_b64encode(db_integration.id.to_bytes(N_BYTES, ENDIAN)).decode()[:-2]
    table_b64 = urlsafe_b64encode(db_table.id.to_bytes(N_BYTES, ENDIAN)).decode()[:-2]

    return RedirectResponse(f"/{integration_b64}/{table_b64}", status_code=301)


@app.get("/{integration_b64}/{table_b64}", response_class=HTMLResponse)
def widget(request: Request, integration_b64: str, table_b64: str, db: Session = Depends(get_db)):
    # Decode the base64 to get the IDs of the integration and table
    try:
        integration_id = int.from_bytes(urlsafe_b64decode((integration_b64 + "==").encode()), ENDIAN)
        table_id = int.from_bytes(urlsafe_b64decode((table_b64 + "==").encode()), ENDIAN)
    except binascii.Error:
        raise PageNotFound()

    # Retrieve the contents of this integration and table from the DB
    db_integration = crud.get_integration(db=db, id=integration_id)
    db_table = crud.get_table(db=db, integration_id=integration_id, id=table_id)

    if db_integration is None or db_table is None:
        raise PageNotFound()

    return templates.TemplateResponse(
        "widget.html", {"request": request, "integration_id": db_integration.token, "table_id": db_table.table_id}
    )


@app.get("/{integration_b64}/{table_b64}/data")
def data(request: Request, integration_b64: str, table_b64: str, db: Session = Depends(get_db)):
    # Decode the base64 to get the IDs of the integration and table
    try:
        integration_id = int.from_bytes(urlsafe_b64decode((integration_b64 + "==").encode()), ENDIAN)
        table_id = int.from_bytes(urlsafe_b64decode((table_b64 + "==").encode()), ENDIAN)
    except binascii.Error:
        raise HTTPException(status_code=404)

    # Retrieve the contents of this integration and table from the DB
    db_integration = crud.get_integration(db=db, id=integration_id)
    db_table = crud.get_table(db=db, integration_id=integration_id, id=table_id)

    if db_integration is None or db_table is None:
        raise HTTPException(status_code=404)

    # Get the data from the Notion API
    notion = Client(auth=db_integration.token)
    properties = []
    for block in iterate_paginated_api(notion.databases.query, database_id=db_table.table_id):
        for b in block:
            properties.append(b["properties"])

    return properties


def serve():
    if config.db == "memory":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
