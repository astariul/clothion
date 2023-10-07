"""Main file, where the FastAPI application and all the routes are declared."""
import binascii
import copy
import json
import pathlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from statistics import mean
from typing import Annotated, List

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from clothion import __version__, config, notion_cache
from clothion.database import SessionLocal, crud


N_BYTES = 4
ENDIAN = "big"


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")


def get_db() -> SessionLocal:
    """FastAPI dependency to create a DB Session.

    Yields:
        SessionLocal: DB Session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class APIException(Exception):
    """Exception raised by the API part of the server, to differentiate from
    HTML exception (which by default return a webpage, but for the API we want
    to return some JSON content).

    Args:
        status_code (int): HTTP code to return.
        detail (str, optional): Error description. Defaults to `None`.
    """

    def __init__(self, status_code: int, detail: str = None):
        self.status_code = status_code
        self.detail = detail


@app.exception_handler(APIException)
async def api_exception_handler(request, exc):
    """Define the exception handler for API exceptions."""
    return await http_exception_handler(request, HTTPException(status_code=exc.status_code, detail=exc.detail))


@app.exception_handler(HTTPException)
async def browser_exception_handler(request, exc):
    """Define the exception handler for HTML exceptions."""
    return templates.TemplateResponse(
        "error.html",
        {"status_code": exc.status_code, "msg": exc.detail, "request": request},
        status_code=exc.status_code,
    )


@app.get("/", tags=["HTML"], response_class=HTMLResponse)
async def welcome(request: Request):
    """Main route, sending the page for table registration."""
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/favicon.ico", tags=["HTML"], include_in_schema=False)
async def favicon():
    """Favicon."""
    return FileResponse(pathlib.Path(__file__).parent / "templates" / "logo.svg")


@app.get("/version", tags=["API"])
async def version() -> str:
    """Returns the current `clothion` version."""
    return __version__


@app.post("/create", tags=["Forms"])
def create(
    integration: Annotated[str, Form()], table: Annotated[str, Form()], db: Session = Depends(get_db)
) -> RedirectResponse:
    """Route to register an integration and a table. Will be called from the
    form of the welcome page.

    If the registration is successful, the user is redirected to the
    integration home page.

    Args:
        integration (Annotated[str, Form]): The integration token to register.
        table (Annotated[str, Form]): The table ID (from Notion) to register.
        db (Session, optional): DB session. Defaults to `Depends(get_db)`.

    Returns:
        RedirectResponse: Redirection.
    """
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
    """For all the routes based on a specific table (like `/xxxx/xxxx`), we
    need to retrieve the proper table from the DB. This class takes care of
    parsing the base64 and retrieving the data from the DB.

    Args:
        integration_b64 (str): Base64 encoding of the integration ID.
        table_b64 (str): Base64 encoding of the table ID.
        db (Session, optional): DB session. Defaults to `Depends(get_db)`.
    """

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
        """Method to call from the HTML routes, to ensure the data was
        successfully retrieved.

        Raises:
            HTTPException: Exception raised if the data doesn't exist in the DB.
        """
        # Ensure the table we seek exists
        if self.integration_id is None or self.table_id is None or self.db_table is None:
            raise HTTPException(status_code=404, detail="Sorry, we couldn't find this page.")

    def error_check_for_api(self):
        """Method to call from the API routes, to ensure the data was
        successfully retrieved.

        Raises:
            HTTPException: Exception raised if the data doesn't exist in the DB.
        """
        # Ensure the table we seek exists
        if self.integration_id is None or self.table_id is None or self.db_table is None:
            raise APIException(status_code=404)


table_router = APIRouter(
    prefix="/{integration_b64}/{table_b64}",
    dependencies=[Depends(ReqTable)],
)


@table_router.get("/", tags=["HTML"], response_class=HTMLResponse)
def build_integration(request: Request, req: ReqTable = Depends(), db: Session = Depends(get_db)):
    """Home page of a specific integration, returning the page for widget
    creation.
    """
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
    """Route doing all the heavylifting with the DB : retrieve the data from
    the local cache (and potentially Notion API). This data can be filtered,
    grouped-by, etc... See `notion_cache.Parameters` for more details.
    """
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
    """Same as `data` route, but only retrieve the schema of a table."""
    # Ensure the table exists
    req.error_check_for_api()

    try:
        return notion_cache.get_schema(db, req.db_table)
    except notion_cache.APIResponseError:
        raise APIException(status_code=422, detail="Error with the Notion API")


@table_router.get("/refresh", tags=["HTML"], response_class=HTMLResponse)
def refresh(request: Request, req: ReqTable = Depends()):
    """A route that allows users to force-refresh their data. After refresh,
    the user is redirected to the home page for their specific table.
    """
    # Ensure the table exists
    req.error_check_for_html()

    return templates.TemplateResponse("refresh.html", {"request": request})


@table_router.get("/panel", tags=["HTML"], response_class=HTMLResponse)
def panel(  # noqa: C901
    request: Request,
    attribute: str = None,
    calculate: str = "sum",
    unit: str = None,
    title: str = None,
    description: str = None,
    is_integer: bool = False,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    """Route creating the Panel widget.

    Args:
        request (Request): Request (used by FastAPI).
        attribute (str, optional): Which attribute to display. Defaults to
            `None`.
        calculate (str, optional): Operation to apply on the data. Defaults to
            "sum".
        unit (str, optional): If specified, the unit to display next to the
            value. Defaults to `None`.
        title (str, optional): If specified, the title to display at the top of
            the panel. Defaults to `None`.
        description (str, optional): If specified, the description to display
            at the bottom of the panel. Defaults to `None`.
        is_integer (bool, optional): If `True`, rounds the value. Defaults to
            `False`.
        update_cache (bool, optional): If set to `False`, uses only the local
            cache, no call to the Notion API is made. Faster, but may fall out
            of sync. Defaults to `True`.
        req (ReqTable, optional): FastAPI Dependency that retrieves the
            integration ID and table ID. Defaults to `Depends()`.
        db (Session, optional): DB Session. Defaults to Depends(get_db).
    """
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


@table_router.get("/panel_monthly", tags=["HTML"], response_class=HTMLResponse)
def panel_monthly(  # noqa: C901
    request: Request,
    attribute: str = None,
    default: int = None,
    calculate: str = "sum",
    date_attribute: str = None,
    day: int = 25,
    filter: str = None,
    unit: str = None,
    title: str = None,
    description: str = None,
    is_integer: bool = False,
    invert_sign: bool = False,
    space_large_number: bool = True,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    """Same as panel route, but compute the monthly value at specific date."""
    # Ensure the table exists
    req.error_check_for_html()

    # Check given parameters
    if attribute is None:
        raise HTTPException(
            status_code=422, detail="You should specify which attribute to use with the query parameter `attribute`."
        )

    if filter is not None:
        # Parse the filter
        try:
            filter = json.loads(filter)
        except json.decoder.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Parameter `filter` is not a valid JSON.")
    else:
        filter = {}

    # Find the right date to keep only data from that date, and update the filter accordingly
    now = datetime.now()
    if now.day >= day:
        d = datetime(now.year, now.month, day)
    else:
        last_month = now.replace(day=1) - timedelta(days=1)
        d = datetime(last_month.year, last_month.month, day)

    if date_attribute is None:
        raise HTTPException(status_code=422, detail="Parameter `date_attribute` not specified.")

    filter[date_attribute] = {"on_or_after": d.isoformat()}

    # Create the proper parameters for the data call
    try:
        params = notion_cache.Parameters(calculate=calculate, filter=filter, update_cache=update_cache)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid calculate function.")

    # Get the data
    try:
        data = notion_cache.get_data(db, req.db_table, params)
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=422, detail="Error with the Notion API.")

    # Extract the value to display
    if attribute not in data:
        if default is not None:
            value = default
        else:
            raise HTTPException(
                status_code=422,
                detail=f"No such attribute (`{attribute}`) in this table. The following attributes are available : "
                f"{list(data.keys())}.",
            )
    else:
        value = data[attribute]

    if value is None:
        raise HTTPException(
            status_code=422, detail=f"Please ensure `{attribute}` is a number, the operation returned `None`."
        )

    # Additional processing
    if is_integer:
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Value (`{value}`) can't be converted to an integer.")
    if invert_sign:
        value = -value
    if space_large_number:
        value = f"{value:,}".replace(",", " ")

    return templates.TemplateResponse(
        "panel.html", {"value": value, "unit": unit, "title": title, "description": description, "request": request}
    )


@table_router.get("/panel_last_x_months", tags=["HTML"], response_class=HTMLResponse)
def panel_last_x_months(  # noqa: C901
    request: Request,
    attribute: str = None,
    default: int = None,
    calculate: str = "sum",
    x: int = 3,
    date_attribute: str = None,
    day: int = 25,
    filter: str = None,
    unit: str = None,
    title: str = None,
    description: str = None,
    is_integer: bool = False,
    invert_sign: bool = False,
    space_large_number: bool = True,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    """Same as panel route, but compute the monthly value at specific date."""
    # Ensure the table exists
    req.error_check_for_html()

    # Check given parameters
    if attribute is None:
        raise HTTPException(
            status_code=422, detail="You should specify which attribute to use with the query parameter `attribute`."
        )

    if filter is not None:
        # Parse the filter
        try:
            filter = json.loads(filter)
        except json.decoder.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Parameter `filter` is not a valid JSON.")
    else:
        filter = {}

    if date_attribute is None:
        raise HTTPException(status_code=422, detail="Parameter `date_attribute` not specified.")

    # We need to do one query for each month
    filters = [copy.deepcopy(filter) for _ in range(x)]

    # Find the right dates for each of the last months
    now = datetime.now()
    if now.day >= day:
        d = datetime(now.year, now.month, day)
    else:
        last_month = now.replace(day=1) - timedelta(days=1)
        d = datetime(last_month.year, last_month.month, day)

    for i in range(x):
        prev_d = (d.replace(day=1) - timedelta(days=1)).replace(day=day)
        filters[i][date_attribute] = {
            "on_or_after": prev_d.isoformat(),
            "before": d.isoformat(),
        }
        d = prev_d

    # Create the proper parameters for the data calls
    try:
        params = [notion_cache.Parameters(calculate=calculate, filter=f, update_cache=update_cache) for f in filters]
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid calculate function.")

    # Get the data
    try:
        data = [notion_cache.get_data(db, req.db_table, p) for p in params]
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=422, detail="Error with the Notion API.")

    # Extract the value to display
    if any(attribute not in result for result in data):
        if default is not None:
            values = [r[attribute] if attribute in r else default for r in data]
        else:
            raise HTTPException(
                status_code=422,
                detail=f"No such attribute (`{attribute}`) in this table. The following attributes are available : "
                f"{list(data.keys())}.",
            )
    else:
        values = [result[attribute] for result in data]

    if any(v is None for v in values):
        raise HTTPException(
            status_code=422, detail=f"Please ensure `{attribute}` is a number, the operation returned `None`."
        )

    # Compute the average
    value = mean(values)

    # Additional processing
    if is_integer:
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Value (`{value}`) can't be converted to an integer.")
    if invert_sign:
        value = -value
    if space_large_number:
        value = f"{value:,}".replace(",", " ")

    return templates.TemplateResponse(
        "panel.html", {"value": value, "unit": unit, "title": title, "description": description, "request": request}
    )


@table_router.get("/chart", tags=["HTML"], response_class=HTMLResponse)
def chart(  # noqa: C901
    request: Request,
    attribute: str = None,
    group_by: str = None,
    chart: str = "bar",
    calculate: str = "sum",
    filter: str = None,
    include: List[str] = Query(default=None),
    exclude: List[str] = Query(default=None),
    invert_sign: bool = False,
    remove_empty: bool = False,
    update_cache: bool = True,
    req: ReqTable = Depends(),
    db: Session = Depends(get_db),
):
    """Route creating the Chart widget.

    Args:
        request (Request): Request (used by FastAPI).
        attribute (str, optional): Which attribute to display. Defaults to
            `None`.
        group_by (str, optional): Which attribute to use for grouping.
            Defaults to `None`.
        chart (str, optional): Type of chart to use. Only `bar` and `pie` is
            available for now. Defaults to `bar`.
        calculate (str, optional): Operation to apply on the data. Defaults to
            "sum".
        filter (str, optional): Filter to use for data filtering, as a JSON
            string. Defaults to `None`.
        include (List[str], optional): List of values to include in the chart.
            Can't be specified together with `exclude`. Defaults to `None`.
        exclude (List[str], optional): List of values to exclude from the
            chart. Can't be specified together with `include`. Defaults to
            `None`.
        invert_sign (bool, optional): If set, invert the sign of the values.
            Defaults to `False`.
        remove_empty (bool, optional): If set, remove values that are 0.
            Defaults to `False`.
        update_cache (bool, optional): If set to `False`, uses only the local
            cache, no call to the Notion API is made. Faster, but may fall out
            of sync. Defaults to `True`.
        req (ReqTable, optional): FastAPI Dependency that retrieves the
            integration ID and table ID. Defaults to `Depends()`.
        db (Session, optional): DB Session. Defaults to Depends(get_db).
    """
    # Ensure the table exists
    req.error_check_for_html()

    # Check given parameters
    if chart not in ["bar", "pie"]:
        raise HTTPException(
            status_code=422, detail=f"Unknown chart type ({chart}). Available chart types : [`bar`, `pie`]."
        )
    if attribute is None:
        raise HTTPException(
            status_code=422, detail="You should specify which attribute to use with the query parameter `attribute`."
        )
    if group_by is None:
        raise HTTPException(
            status_code=422, detail="You should specify how to group the data with the query parameter `group_by`."
        )

    if filter is not None:
        # Parse the filter
        try:
            filter = json.loads(filter)
        except json.decoder.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Parameter `filter` is not a valid JSON.")

    # Create the proper parameters for the data call
    try:
        params = notion_cache.Parameters(
            calculate=calculate, group_by=group_by, filter=filter, update_cache=update_cache
        )
    except ValidationError:
        raise HTTPException(status_code=422, detail="Invalid calculate function.")

    # Get the data
    try:
        data = notion_cache.get_data(db, req.db_table, params)
    except notion_cache.APIResponseError:
        raise HTTPException(status_code=422, detail="Error with the Notion API.")
    except crud.WrongFilter as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error with the `filter` argument : {str(e)}",
        )

    # Check the results, if something went wrong tell the possible cause
    if len(data) == 0:
        raise HTTPException(
            status_code=422,
            detail=f"Either `group_by` parameter is invalid or `filter` parameter is too restrictive : "
            f"no data found for `{group_by}` in the Notion table.",
        )
    d = list(data.values())[0]
    if attribute not in d:
        raise HTTPException(
            status_code=422,
            detail=f"No such attribute (`{attribute}`) in this table. The following attributes are available : "
            f"{list(d.keys())}.",
        )
    if all(d[attribute] is None for d in data.values()):
        raise HTTPException(
            status_code=422,
            detail=f"No number found for `{attribute}`. Make sure this attribute is a number and the table contains "
            f"some data.",
        )

    # Additional filtering
    if include is not None:
        displayed_groups = include
    else:
        displayed_groups = list(data.keys())

    if exclude is not None:
        displayed_groups = [g for g in displayed_groups if g not in exclude]

    data = {k: v[attribute] for k, v in data.items() if k in displayed_groups}

    # Deal with None values
    data = {k: v for k, v in data.items() if v is not None}

    # Additional processing
    if invert_sign:
        data = {k: -v for k, v in data.items()}

    if remove_empty:
        data = {k: v for k, v in data.items() if v != 0}

    # Handle potential None key
    data = {str(k) if k is not None else "null": v for k, v in data.items()}

    return templates.TemplateResponse("chart.html", {"data": data, "chart": chart, "request": request})


app.include_router(table_router)


@app.route("/{full_path:path}")
async def unknown_path(request: Request):
    """Catch-all route, if the user tries to access an unknown page, we display
    a 404.
    """
    raise HTTPException(status_code=404, detail="Sorry, we couldn't find this page.")


def serve():
    """The function called to run the server.

    It will simply run the FastAPI app. Also, if the selected DB is in-memory,
    it will ensure the tables are created.
    """
    if config.db == "memory":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
