import binascii
import pathlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from clothion import __version__, config, notion_cache
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


@app.get("/", tags=["HTML"], response_class=HTMLResponse)
async def welcome(request: Request):
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/favicon.ico", tags=["HTML"], include_in_schema=False)
async def favicon():
    return FileResponse(pathlib.Path(__file__).parent / "templates" / "logo.svg")


@app.get("/version", tags=["API"])
async def version() -> str:
    return __version__


@app.post("/create", tags=["Forms"])
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

    return RedirectResponse(f"/{integration_b64}/{table_b64}/", status_code=301)


class ReqTable:
    def __init__(self, integration_b64: str, table_b64: str, db: Session = Depends(get_db)):
        self.db = db

        # Decode the base64 to get the IDs of the integration and table
        try:
            self.integration_id = int.from_bytes(urlsafe_b64decode((integration_b64 + "==").encode()), ENDIAN)
            self.table_id = int.from_bytes(urlsafe_b64decode((table_b64 + "==").encode()), ENDIAN)
        except binascii.Error:
            raise PageNotFound()

    def get_integration_db(self):
        return crud.get_integration(db=self.db, id=self.integration_id)

    def get_table_db(self):
        return crud.get_table(db=self.db, integration_id=self.integration_id, id=self.table_id)


table_router = APIRouter(
    prefix="/{integration_b64}/{table_b64}",
    dependencies=[Depends(ReqTable)],
)


@table_router.get("/", tags=["HTML"], response_class=HTMLResponse)
def widget(request: Request, req: ReqTable = Depends()):
    # Retrieve the contents of this integration and table from the DB
    db_integration = req.get_integration_db()
    db_table = req.get_table_db()

    if db_integration is None or db_table is None:
        raise PageNotFound()

    return templates.TemplateResponse(
        "widget.html", {"request": request, "integration_id": db_integration.token, "table_id": db_table.table_id}
    )


@table_router.get("/data", tags=["API"])
def data(
    reset_cache: bool = False,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    # Retrieve the contents of this integration and table from the DB
    db_integration = req.get_integration_db()
    db_table = req.get_table_db()

    if db_integration is None or db_table is None:
        raise HTTPException(status_code=404)

    try:
        return notion_cache.get_data(
            db,
            db_integration.token,
            db_table.table_id,
            db_table.id,
            reset_cache=reset_cache,
            update_cache=update_cache,
        )
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=404)


@table_router.get("/schema", tags=["API"])
def schema(req: ReqTable = Depends()):
    # Retrieve the contents of this integration and table from the DB
    db_integration = req.get_integration_db()
    db_table = req.get_table_db()

    if db_integration is None or db_table is None:
        raise HTTPException(status_code=404)

    try:
        return notion_cache.get_schema(db_integration.token, db_table.table_id)
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=404)


app.include_router(table_router)


def serve():
    if config.db == "memory":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
