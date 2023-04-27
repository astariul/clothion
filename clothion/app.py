import uvicorn
from fastapi import FastAPI

from clothion import __version__


app = FastAPI(title="Clothion", version=__version__, redoc_url=None)


@app.get("/", tags=["API"])
async def root():
    return {"message": "Hello World"}


def serve():
    """Main function, serving the app."""
    uvicorn.run(app)
