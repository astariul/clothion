import uvicorn
from fastapi import FastAPI

from clothion import __version__, config


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)


@app.get("/version", tags=["API"])
async def version() -> str:
    return __version__


def serve():
    """Main function, serving the app."""
    uvicorn.run(app, host=config.host, port=config.port)
