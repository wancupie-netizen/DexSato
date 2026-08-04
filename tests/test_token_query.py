"""
DexSato Engineering Test

Token Query Integration Test

Purpose
-------
Verify Product Layer integration.

Flow

TokenQuery
    ↓
TokenQueryService
    ↓
Intelligence Store
    ↓
Deserializer
    ↓
Assembler
    ↓
Mapper
    ↓
DTO
"""

from pprint import pprint

from application.queries.token_query import TokenQuery
from application.assemblers.token_assembler import TokenAssembler


print("=" * 60)
print("DexSato Product Layer Test")
print("=" * 60)

query = TokenQuery()

assembler = TokenAssembler()

print("\nLoading BTC...\n")

payload = query.get_token("BTC")

print("Payload")
print("-" * 60)

pprint(payload)

print("\nBuilding DTO...\n")

dto = assembler.assemble(payload)

print("DTO")
print("-" * 60)

print(dto)

print("\nPASS")