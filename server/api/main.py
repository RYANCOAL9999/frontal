import os
import uvicorn
from routers import frontal
from dotenv import load_dotenv
from database import engine, Base
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import PrometheusFastApiInstrumentator

load_dotenv()

API_FULL_VERSION = os.getenv("API_VERSION", "1.0.0")

API_MAJOR_VERSION = API_FULL_VERSION.split(".")[0]

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Crop Submission API",
    description="API for processing frontal crop submissions.",
    version=API_FULL_VERSION,
)

PrometheusFastApiInstrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_group_untemplated=False,
    excluded_handlers=["/metrics", "/admin"],
    buckets=[1, 2, 3, 4, 5],
    metric_name="my_custom_metric_name",
    label_names=(
        "method_type",
        "path",
        "status_code",
    ),
).instrument(app).expose(app, "/prometheus_metrics")

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
