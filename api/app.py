"""
DexSato API

Main entry point for the DexSato Platform.

Responsibilities
----------------
- Create FastAPI application.
- Register API routers.
- Expose OpenAPI documentation.
- Contain no business logic.
"""

from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.token import router as token_router


# ==========================================================
# Application
# ==========================================================

app = FastAPI(

    title="DexSato API",

    description=(
        "Evidence-Driven Intelligence Platform "
        "for Digital Asset Monitoring."
    ),

    version="0.9.0-alpha",

    docs_url="/docs",

    redoc_url="/redoc",

    openapi_url="/openapi.json",

)

# ==========================================================
# Routes
# ==========================================================

app.include_router(health_router)

app.include_router(token_router)