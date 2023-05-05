import pathlib
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from clothion import __version__, config
from clothion.database import SessionLocal, crud


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)

templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
def create(integration: Annotated[str, Form()], table: Annotated[str, Form()], db: Session = Depends(get_db)) -> int:
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

    return RedirectResponse(f"/{db_integration.id}/{db_table.id}", status_code=301)


@app.get("/{integration_id}/{table_id}", response_class=HTMLResponse)
def widget(request: Request, integration_id: int, table_id: int):
    return templates.TemplateResponse(
        "widget.html", {"request": request, "integration_id": integration_id, "table_id": table_id}
    )


def serve():
    if config.db == "memory":
        crud.create_tables()

    uvicorn.run(app, host=config.host, port=config.port)
