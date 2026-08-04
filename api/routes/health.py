"""
DexSato Health Route

Health endpoint for service monitoring.

Responsibilities
----------------
- Report API availability.
- Report service version.
- Contain no business logic.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1",
    tags=["System"],
)


@router.get("/health")
def health():

    return {

        "status": "ok",

        "service": "DexSato API",

        "version": "0.9.0-alpha",

    }