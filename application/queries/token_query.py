"""
DexSato Token Query

Application Query responsible for retrieving
Token Detail data.

Responsibilities
----------------
- Coordinate Token retrieval.
- Delegate retrieval to TokenQueryService.
- Remain storage independent.
- Contain no business logic.
"""

from application.queries.base_query import (
    BaseQuery,
)

from application.services.token_query_service import (
    TokenQueryService,
)


class TokenQuery(BaseQuery):
    """
    Official Token Query.
    """

    def __init__(self):

        self._service = TokenQueryService()

    def get_token(
        self,
        symbol: str,
    ) -> dict | None:
        """
        Retrieve Token Detail payload.

        Parameters
        ----------
        symbol : str

        Returns
        -------
        dict | None
        """

        return self._service.get_token(
            symbol,
        )