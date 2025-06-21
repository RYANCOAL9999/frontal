import os
import uvicorn
from routers import frontal
from dotenv import load_dotenv
from database import engine, Base
from fastapi import FastAPI, Request

load_dotenv()

API_FULL_VERSION = os.getenv("API_VERSION", "1.0.0")

API_MAJOR_VERSION = API_FULL_VERSION.split(".")[0]

app = FastAPI(
    title="Crop Submission API",
    description="API for processing frontal crop submissions.",
    version=API_FULL_VERSION,
)

Base.metadata.create_all(bind=engine)

app.include_router(frontal.router, prefix=f"/api/v{API_MAJOR_VERSION}/frontal")


@app.get("/")
async def read_root(request: Request):
    return {
        "message": "Welcome to the frontal API!",
        "api_version": API_FULL_VERSION,
        "docs_url": f"{str(request.url)}docs",
    }


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("APP_HOST"), port=int(os.getenv("APP_PORT")))
