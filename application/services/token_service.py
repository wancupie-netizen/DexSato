"""
DexSato Token Service

Application Service responsible for the
Token Detail use case.

Responsibilities
----------------
- Execute the Token Detail use case.
- Coordinate Query and Assembler.
- Return TokenDetailDTO.
- Remain independent of HTTP.
- Contain no business logic.
"""

from application.assemblers.token_assembler import (
    TokenAssembler,
)

from application.dto.token_detail_dto import (
    TokenDetailDTO,
)

from application.queries.token_query import (
    TokenQuery,
)


class TokenService:
    """
    Token Detail Application Service.
    """

    def __init__(self):

        self._query = TokenQuery()

        self._assembler = TokenAssembler()

    def get_token_detail(

        self,

        symbol: str,

    ) -> TokenDetailDTO:
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

        payload = self._query.get_token(

            symbol=symbol,

        )

        return self._assembler.assemble(

            payload,

        )