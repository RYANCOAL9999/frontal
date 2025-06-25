import os
import uvicorn
from routers import frontal
from dotenv import load_dotenv
from services.logger import console
from fastapi import FastAPI, Request
from prometheus_client import generate_latest
from services.worker import startup_db_and_worker, shutdown_worker
from starlette_exporter import PrometheusMiddleware, handle_metrics

# Load environment variables from .env file
load_dotenv()

# Set API version from environment variable or default to "1.0.0"
API_FULL_VERSION = os.getenv("API_VERSION", "1.0.0")

# Extract major version from the full version string
API_MAJOR_VERSION = API_FULL_VERSION.split(".")[0]

# Check if load testing mode is enabled via environment variable
LOADTEST_MODE_ENABLED = os.getenv("LOADTEST_MODE", "false").lower() == "true"
if LOADTEST_MODE_ENABLED:
    console.log(
        "[bold magenta]Load testing mode is ENABLED: Processing delay will be skipped.[/bold magenta]"
    )
else:
    console.log(
        "[dim cyan]Load testing mode is DISABLED: Processing delay will be active.[/dim cyan]"
    )

# Initialize FastAPI application with title, description, and version
app = FastAPI(
    title="Crop Submission API",
    description="API for processing frontal crop submissions.",
    version=API_FULL_VERSION,
)

# Add Prometheus middleware for metrics collection
app.add_middleware(
    PrometheusMiddleware,
    app_name="frontal_api",
    prefix="frontal_api",
    filter_unhandled_paths=True,
    skip_paths=["/metrics"],
)


# Endpoint to expose Prometheus metrics
@app.get("/metrics", include_in_schema=False)
async def metrics() -> str:
    return handle_metrics(generate_latest())


# Startup and shutdown events for the FastAPI application
@app.on_event("startup")
async def startup_event() -> None:
    console.log("[bold green]Application startup initiated.[/bold green]")
    await startup_db_and_worker(app, LOADTEST_MODE_ENABLED)
    console.log("[bold green]Application startup complete.[/bold green]")


# Shutdown event to gracefully stop the worker
@app.on_event("shutdown")
async def shutdown_event() -> None:
    console.log("[bold red]Application shutdown initiated.[/bold red]")
    await shutdown_worker(app)
    console.log("[bold red]Application shutdown complete.[/bold red]")


# Include the frontal router with the specified API version prefix
app.include_router(frontal.router, prefix=f"/api/v{API_MAJOR_VERSION}/frontal")


# Root endpoint to provide basic information about the API
@app.get("/")
async def read_root(request: Request) -> dict:
    return {
        "message": "Welcome to the frontal API!",
        "api_version": API_FULL_VERSION,
        "docs_url": f"{str(request.url)}docs",
    }


# Main entry point to run the FastAPI application using Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("APP_HOST"), port=int(os.getenv("APP_PORT")))
