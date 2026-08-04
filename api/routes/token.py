"""
DexSato Token Route

Token API endpoints.

Responsibilities
----------------
- Accept HTTP requests.
- Delegate work to Application Services.
- Return DTO responses.
- Contain no business logic.
"""

from fastapi import APIRouter

from application.services.token_service import (
    TokenService,
)

router = APIRouter(
    prefix="/api/v1/tokens",
    tags=["Tokens"],
)

service = TokenService()


@router.get("/{symbol}")
def get_token(

    symbol: str,

):
    """
    Retrieve Token Detail.

    Parameters
    ----------
    symbol
        Token symbol.

    Returns
    -------
    TokenDetailDTO
    """

    return service.get_token_detail(

        symbol=symbol.upper(),

    )