"""
DexSato Token Assembler

Application Assembler responsible for converting
Token Query data into TokenDetailDTO.

Responsibilities
----------------
- Assemble Token Detail DTO.
- Delegate DTO construction to the Token Mapper.
- Remain independent of HTTP.
- Contain no business logic.
"""

from application.dto.token_detail_dto import (
    TokenDetailDTO,
)

from application.mappers.token_mapper import (
    build_token_detail,
)


class TokenAssembler:
    """
    Assemble Token Detail DTO.
    """

    def assemble(

        self,

        payload: dict,

    ) -> TokenDetailDTO:
        """
        Assemble a Token Detail DTO from
        Query payload.
        """

        return build_token_detail(

            header=payload["header"],

            observation=payload["observation"],

            signals=payload["signals"],

            interpretations=payload["interpretations"],

            decision=payload["decision"],

            outcome=payload["outcome"],

            learning=payload["learning"],

            knowledge=payload["knowledge"],

        )