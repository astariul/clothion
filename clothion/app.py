import binascii
import pathlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic.error_wrappers import ValidationError
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


class APIException(Exception):
    def __init__(self, status_code: int, detail: str = None):
        self.status_code = status_code
        self.detail = detail


@app.exception_handler(APIException)
async def api_exception_handler(request, exc):
    return await http_exception_handler(request, HTTPException(status_code=exc.status_code, detail=exc.detail))


@app.exception_handler(HTTPException)
async def browser_exception_handler(request, exc):
    return templates.TemplateResponse(
        "error.html",
        {"status_code": exc.status_code, "msg": exc.detail, "request": request},
        status_code=exc.status_code,
    )


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
            self.integration_id = None
            self.table_id = None
        else:
            self.db_table = crud.get_table(db=self.db, integration_id=self.integration_id, id=self.table_id)

    def error_check_for_html(self):
        # Ensure the table we seek exists
        if self.integration_id is None or self.table_id is None or self.db_table is None:
            raise HTTPException(status_code=404, detail="Sorry, we couldn't find this page.")

    def error_check_for_api(self):
        # Ensure the table we seek exists
        if self.integration_id is None or self.table_id is None or self.db_table is None:
            raise APIException(status_code=404)


table_router = APIRouter(
    prefix="/{integration_b64}/{table_b64}",
    dependencies=[Depends(ReqTable)],
)


@table_router.get("/", tags=["HTML"], response_class=HTMLResponse)
def build_integration(request: Request, req: ReqTable = Depends(), db: Session = Depends(get_db)):
    # Ensure the table exists
    req.error_check_for_html()

    try:
        schema = notion_cache.get_schema(db, req.db_table)
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=422, detail="Error with the Notion API.")

    return templates.TemplateResponse("build.html", {"schema": schema, "request": request})


@table_router.post("/data", tags=["API"])
def data(
    parameters: notion_cache.Parameters,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    # Ensure the table exists
    req.error_check_for_api()

    try:
        return notion_cache.get_data(db, req.db_table, parameters)
    except notion_cache.APIResponseError:
        raise APIException(status_code=422, detail="Error with the Notion API")
    except notion_cache.TooMuchAttributes:
        raise APIException(
            status_code=413,
            detail=f"Your data contains more than {notion_cache.MAX_ATTRIBUTES} attributes. Clothion has a limit on "
            "the amount of data it can answer with, please use filters to retrieve only the data you need.",
        )
    except crud.WrongFilter as e:
        raise APIException(
            status_code=422,
            detail=f"Error with the `filter` argument : {str(e)}",
        )


@table_router.get("/schema", tags=["API"])
def schema(req: ReqTable = Depends(), db: Session = Depends(get_db)):
    # Ensure the table exists
    req.error_check_for_api()

    try:
        return notion_cache.get_schema(db, req.db_table)
    except notion_cache.APIResponseError:
        raise APIException(status_code=422, detail="Error with the Notion API")


@table_router.get("/refresh", tags=["HTML"], response_class=HTMLResponse)
def refresh(request: Request, req: ReqTable = Depends()):
    # Ensure the table exists
    req.error_check_for_html()

    return templates.TemplateResponse("refresh.html", {"request": request})


@table_router.get("/panel", tags=["HTML"], response_class=HTMLResponse)
def panel(  # noqa: C901
    request: Request,
    calculate: str = "sum",
    attribute: str = None,
    unit: str = None,
    title: str = None,
    description: str = None,
    is_integer: bool = False,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    # Ensure the table exists
    req.error_check_for_html()

    # Check given parameters
    if attribute is None:
        raise HTTPException(
            status_code=422, detail="You should specify which attribute to use with the query parameter `attribute`."
        )

    # Create the proper parameters for the data call
    try:
        params = notion_cache.Parameters(calculate=calculate, update_cache=update_cache)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid calculate function.")

    # Get the data
    try:
        data = notion_cache.get_data(db, req.db_table, params)
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=422, detail="Error with the Notion API.")

    # Extract the value to display
    if attribute not in data:
        raise HTTPException(
            status_code=422,
            detail=f"No such attribute (`{attribute}`) in this table. The following attributes are available : "
            f"{list(data.keys())}.",
        )

    value = data[attribute]

    if value is None:
        raise HTTPException(
            status_code=422, detail=f"Please ensure `{attribute}` is a number, the operation returned `None`."
        )

    if is_integer:
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Value (`{value}`) can't be converted to an integer.")

    return templates.TemplateResponse(
        "panel.html", {"value": value, "unit": unit, "title": title, "description": description, "request": request}
    )


app.include_router(table_router)


@app.route("/{full_path:path}")
async def unknown_path(request: Request):
    raise HTTPException(status_code=404, detail="Sorry, we couldn't find this page.")


def serve():
    if config.db == "memory":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
