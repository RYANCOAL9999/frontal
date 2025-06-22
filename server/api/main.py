import os
import uvicorn
from routers import frontal
from dotenv import load_dotenv
from services.logger import console
from fastapi import FastAPI, Request
from prometheus_client import generate_latest
from services.worker import startup_db_and_worker, shutdown_worker
from starlette_exporter import PrometheusMiddleware, handle_metrics

load_dotenv()

API_FULL_VERSION = os.getenv("API_VERSION", "1.0.0")

API_MAJOR_VERSION = API_FULL_VERSION.split(".")[0]

LOADTEST_MODE_ENABLED = os.getenv("LOADTEST_MODE", "false").lower() == "true"
if LOADTEST_MODE_ENABLED:
    console.log("[bold magenta]Load testing mode is ENABLED: Processing delay will be skipped.[/bold magenta]")
else:
    console.log("[dim cyan]Load testing mode is DISABLED: Processing delay will be active.[/dim cyan]")

app = FastAPI(
    title="Crop Submission API",
    description="API for processing frontal crop submissions.",
    version=API_FULL_VERSION,
)

app.add_middleware(
    PrometheusMiddleware,
    app_name="frontal_api",
    prefix="frontal_api",
    filter_unhandled_paths=True,
    skip_paths=["/metrics"],
)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return handle_metrics(generate_latest())


@app.on_event("startup")
async def startup_event():
    console.log("[bold green]Application startup initiated.[/bold green]")
    await startup_db_and_worker(app, LOADTEST_MODE_ENABLED)
    console.log("[bold green]Application startup complete.[/bold green]")


@app.on_event("shutdown")
async def shutdown_event():
    console.log("[bold red]Application shutdown initiated.[/bold red]")
    await shutdown_worker(app)
    console.log("[bold red]Application shutdown complete.[/bold red]")


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
