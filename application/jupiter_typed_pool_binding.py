"""Read-only, legacy SPL-token pool/vault bindings. Never execution approval.

Scope: DLMM swap, Saber swap, Whirlpool swap; not swap_v2, Token-2022,
tick/bin price math, deployed-bytecode equivalence, or historical state proof.
"""
import hashlib
from application.jupiter_pool_validation import (
    TOKEN, WSOL, USDC, require, key, b58decode, b58encode, raw_account,
    token_vault, pda, BindingRejected,
)

METEORA = 'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo'
SABER = 'SSwpkEEcbUqx4vtoEByFjSkhKdCT862DNVb52nZg1UZ'
ORCA = 'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc'
USDT = 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
PROGRAMS = frozenset((METEORA, SABER, ORCA))
SOURCES = {
    METEORA: 'https://github.com/MeteoraAg/dlmm-sdk/blob/fb02e51ae677bbd18e76543f702dae40632426db/idls/dlmm.json',
    SABER: 'https://github.com/saber-hq/stable-swap/blob/39d5d4e0e844a009c83d37a3ce63d219fdba0bff/stable-swap-client/src/state.rs',
    ORCA: 'https://github.com/orca-so/whirlpools/blob/3b47341e16110ba015ca0acf06a53c0fa12e49f3/programs/whirlpool/src/state/whirlpool.rs',
}


def at(raw, offset):
    return b58encode(raw[offset:offset+32])


def decode_call(ix):
    require(isinstance(ix, dict) and ix.get('programId') in PROGRAMS
            and type(ix.get('stackHeight')) is int and ix['stackHeight'] == 2,
            'TYPED_DIRECT_CPI_REQUIRED')
    program = ix['programId']; a = ix.get('accounts')
    require(isinstance(a, list) and 9 <= len(a) <= 32, 'TYPED_ACCOUNT_COUNT')
    for address in a:
        key(address)
    data = b58decode(ix.get('data'), 128)
    swap = hashlib.sha256(b'global:swap').digest()[:8]
    if program == METEORA:
        require(16 <= len(a) <= 32 and len(data) == 24 and data[:8] == swap,
                'DLMM_LEGACY_SWAP_REQUIRED')
        require(a[11] == a[12] == TOKEN and a[14] == METEORA
                and a[9] == METEORA, 'DLMM_TOKEN_PROGRAM_OR_HOST_FEE')
        require(a[13] == pda([b'__event_authority'], METEORA), 'DLMM_EVENT_AUTHORITY')
        pool, authority, source, destination, v0, v1 = 0, 10, 4, 5, 2, 3
        extra = []; offset = 8
    elif program == SABER:
        require(len(a) == 9 and len(data) == 17 and data[0] == 1 and a[8] == TOKEN,
                'SABER_LEGACY_SWAP_REQUIRED')
        pool, authority, source, destination, v0, v1 = 0, 2, 3, 6, 4, 5
        extra = [a[7]]; offset = 1
    else:
        require(len(a) == 11 and len(data) == 42 and data[:8] == swap
                and data[40] == 1 and data[41] in (0, 1) and a[0] == TOKEN,
                'ORCA_LEGACY_EXACT_INPUT_REQUIRED')
        pool, authority, v0, v1 = 2, 1, 4, 6
        source, destination = (3, 5) if data[41] else (5, 3)
        extra = []; offset = 8
    amount = int.from_bytes(data[offset:offset+8], 'little')
    require(amount > 0, 'TYPED_ZERO_INPUT')
    addresses = [a[pool], a[v0], a[v1], a[source], a[destination]] + extra + [program]
    require(len(set(addresses)) == len(addresses), 'TYPED_CRITICAL_ACCOUNT_ALIAS')
    return dict(program=program, pool=a[pool], authority=a[authority],
                source=a[source], destination=a[destination], addresses=addresses,
                amount_in=amount, leg_minimum=int.from_bytes(data[offset+8:offset+16], 'little'),
                a_to_b=bool(data[41]) if program == ORCA else None)


def validate_snapshot(ix, snapshot, addresses, minimum_slot, route_authority, known):
    call = decode_call(ix); a = ix['accounts']; program = call['program']
    require(set(a).issubset(known) and program in known, 'TYPED_ACCOUNT_OUTSIDE_MESSAGE')
    require(call['authority'] == route_authority, 'TYPED_JUPITER_AUTHORITY')
    require(addresses == call['addresses'], 'TYPED_SNAPSHOT_ADDRESS_ORDER')
    require(isinstance(snapshot, dict) and isinstance(snapshot.get('context'), dict), 'TYPED_SNAPSHOT_ENVELOPE')
    slot = snapshot['context'].get('slot'); values = snapshot.get('value')
    require(type(minimum_slot) is int and minimum_slot >= 0 and type(slot) is int
            and slot >= minimum_slot, 'TYPED_STALE_SNAPSHOT')
    require(isinstance(values, list) and len(values) == len(addresses), 'TYPED_SNAPSHOT_COUNT')
    executable = values[-1]
    require(isinstance(executable, dict) and executable.get('executable') is True
            and executable.get('owner') == 'BPFLoaderUpgradeab1e11111111111111111111111',
            'TYPED_PROGRAM_NOT_EXECUTABLE')
    raw = raw_account(values[0], program, {METEORA: 904, SABER: 395, ORCA: 653}[program])
    admin = None
    if program == METEORA:
        require(raw[:8] == hashlib.sha256(b'account:LbPair').digest()[:8], 'DLMM_DISCRIMINATOR')
        require(raw[82] == 0 and raw[880:882] == bytes(2), 'DLMM_DISABLED_OR_TOKEN2022')
        m0, m1, v0, v1 = (at(raw, p) for p in (88, 120, 152, 184))
        require((m0, m1, v0, v1) == (a[6], a[7], a[2], a[3]), 'DLMM_POOL_FIELDS')
        require(at(raw, 552) == a[8] == pda([b'oracle', key(a[0])], program), 'DLMM_ORACLE_BINDING')
        for mint, vault in ((m0, v0), (m1, v1)):
            require(vault == pda([key(a[0]), key(mint)], program), 'DLMM_RESERVE_PDA')
        # Pool variants have different creation seeds. Ownership/discriminator,
        # stored reserves and reserve PDAs are checked; pool origin is not claimed.
        pool_authority = a[0]
        source_raw = raw_account(values[3], TOKEN, 165)
        input_mint = at(source_raw, 0)
        require(input_mint in (m0, m1) and m0 != m1, 'DLMM_INPUT_MINT')
        forward = input_mint == m0
    elif program == SABER:
        require(raw[0:2] == b'\x01\x00', 'SABER_UNINITIALIZED_OR_PAUSED')
        m0, m1, v0, v1 = (at(raw, p) for p in (203, 235, 107, 139))
        require((a[4], a[5]) in ((v0, v1), (v1, v0)) and v0 != v1 and m0 != m1,
                'SABER_RESERVE_BINDING')
        from solders.pubkey import Pubkey
        try:
            pool_authority = str(Pubkey.create_program_address([key(a[0]), raw[2:3]], Pubkey.from_string(program)))
        except Exception:
            raise BindingRejected('SABER_NONCE_PDA') from None
        require(pool_authority == a[1], 'SABER_AUTHORITY_PDA')
        forward = a[4] == v0
        require(a[7] == at(raw, 299 if forward else 267), 'SABER_ADMIN_FEE_ADDRESS')
        admin_raw = raw_account(values[5], TOKEN, 165)
        admin = token_vault(values[5], m1 if forward else m0, at(admin_raw, 32))
    else:
        require(raw[:8] == hashlib.sha256(b'account:Whirlpool').digest()[:8], 'ORCA_DISCRIMINATOR')
        m0, m1, v0, v1 = (at(raw, p) for p in (101, 181, 133, 213))
        require(a[4] == v0 and a[6] == v1 and key(m0) < key(m1), 'ORCA_POOL_FIELDS')
        require(a[2] == pda([b'whirlpool', raw[8:40], key(m0), key(m1), raw[43:45]], program), 'ORCA_POOL_PDA')
        require(a[10] == pda([b'oracle', key(a[2])], program), 'ORCA_ORACLE_PDA')
        pool_authority = a[2]; forward = call['a_to_b']
    input_mint, output_mint = (m0, m1) if forward else (m1, m0)
    # Narrow audit profile only. This does not restrict production token choice.
    require(input_mint != output_mint and {input_mint, output_mint}.issubset({WSOL, USDC, USDT}), 'TYPED_AUDIT_MINT_PROFILE')
    input_vault, output_vault = (v0, v1) if forward else (v1, v0)
    vault_map = dict(zip(addresses[1:3], values[1:3]))
    vault_in = token_vault(vault_map[input_vault], input_mint, pool_authority)
    vault_out = token_vault(vault_map[output_vault], output_mint, pool_authority)
    token_vault(values[3], input_mint, route_authority)
    token_vault(values[4], output_mint, route_authority)
    return {**call, 'status': 'TYPED_POOL_VAULT_BINDING_MATCHED',
            'snapshot_slot': slot, 'source_reference': SOURCES[program],
            'pool_data_sha256': hashlib.sha256(raw).hexdigest(),
            'input_mint': input_mint, 'output_mint': output_mint,
            'input_vault': input_vault, 'output_vault': output_vault,
            'pool_authority': pool_authority, 'vault_in': vault_in, 'vault_out': vault_out,
            'admin_fee_account': a[7] if program == SABER else None,
            'admin_fee_snapshot': admin, 'execution_ready': False,
            'deployed_bytecode_verified': False,
            'scope': 'Pool fields, token accounts, authority, CPI direction; not tick/bin math or historical state.'}


def validate_children(binding, children):
    """Bind all returned child transfers. Unknown instructions never disappear."""
    require(isinstance(children, list) and len(children) <= 32, 'TYPED_CHILD_COUNT')
    transfers = []; events = 0
    for ix in children:
        require(isinstance(ix, dict) and type(ix.get('stackHeight')) is int
                and ix['stackHeight'] == 3, 'TYPED_CHILD_DEPTH')
        if ix.get('programId') == METEORA and binding['program'] == METEORA:
            data = b58decode(ix.get('data'), 2048)
            require(ix.get('accounts') == [pda([b'__event_authority'], METEORA)]
                    and len(data) >= 16 and data[:8].hex() == 'e445a52e51cb9a1d', 'DLMM_UNRECOGNIZED_CHILD')
            events += 1
            continue  # Event envelope only, not semantic verification of event payload.
        require(ix.get('programId') == TOKEN and isinstance(ix.get('parsed'), dict), 'TYPED_UNKNOWN_CHILD')
        parsed = ix['parsed']; info = parsed.get('info')
        require(parsed.get('type') in ('transfer', 'transferChecked') and isinstance(info, dict)
                and 'multisigAuthority' not in info and 'signers' not in info, 'TYPED_TRANSFER_FORMAT')
        value = info.get('amount') if parsed['type'] == 'transfer' else info.get('tokenAmount', {}).get('amount')
        require(isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 20
                and int(value) < 2**64, 'TYPED_TRANSFER_AMOUNT')
        edge = (info.get('source'), info.get('destination'), info.get('authority'))
        edges = [(binding['source'], binding['input_vault'], binding['authority']),
                 (binding['output_vault'], binding['destination'], binding['pool_authority'])]
        if binding['admin_fee_account']:
            edges.append((binding['output_vault'], binding['admin_fee_account'], binding['pool_authority']))
        require(edge in edges, 'TYPED_TRANSFER_EDGE')
        index = edges.index(edge)
        if parsed['type'] == 'transferChecked':
            mint = binding['input_mint'] if index == 0 else binding['output_mint']
            require(info.get('mint') == mint and type(info['tokenAmount'].get('decimals')) is int
                    and info['tokenAmount']['decimals'] == (9 if mint == WSOL else 6), 'TYPED_TRANSFER_MINT')
        transfers.append((index, int(value)))
    expected = [0, 1, 2] if binding['program'] == SABER else [0, 1]
    require([i for i, _ in transfers] == expected, 'TYPED_TRANSFER_SEQUENCE')
    require(transfers[0][1] == binding['amount_in'] and transfers[1][1] > 0
            and transfers[1][1] >= binding['leg_minimum'], 'TYPED_TRANSFER_AMOUNTS')
    return {'status': 'CHILD_TRANSFER_BINDING_MATCHED', 'input_raw': str(transfers[0][1]),
            'output_raw': str(transfers[1][1]), 'event_envelopes': events,
            'event_payload_semantics_verified': False, 'execution_ready': False}


def audit_typed_calls(inner, known, route_authority, minimum_slot, fetch):
    """fetch(addresses, min_slot) is injected; production caller uses read-only RPC."""
    require(isinstance(inner, list) and len(inner) <= 256, 'TYPED_INNER_LIMIT')
    results = []; covered = set()
    for index, ix in enumerate(inner):
        if ix.get('programId') not in PROGRAMS or ix.get('stackHeight') != 2:
            continue
        end = index + 1
        while end < len(inner) and type(inner[end].get('stackHeight')) is int and inner[end]['stackHeight'] > 2:
            end += 1
        try:
            call = decode_call(ix)
            require(set(ix['accounts']).issubset(known) and call['program'] in known, 'TYPED_ACCOUNT_OUTSIDE_MESSAGE')
            require(call['authority'] == route_authority, 'TYPED_JUPITER_AUTHORITY')
            snapshot = fetch(call['addresses'], minimum_slot)
            binding = validate_snapshot(ix, snapshot, call['addresses'], minimum_slot, route_authority, known)
            children = validate_children(binding, inner[index+1:end])
            results.append({'ordinal': index, 'binding': binding, 'children': children,
                            'snapshot_addresses': call['addresses'], 'snapshot': snapshot})
            covered.update(range(index, end))
        except BindingRejected as exc:
            results.append({'ordinal': index, 'program': ix.get('programId'),
                            'status': 'TYPED_BINDING_NOT_MATCHED', 'reason': str(exc), 'execution_ready': False})
    return results, covered


def validate_route_links(rows, route_source, route_destination):
    """Captured split-route profile: WSOL->USDT->USDC plus WSOL->USDC.

    A different topology needs review, not silent reuse of this audit profile.
    """
    require(len(rows) == 3 and all('binding' in row and 'children' in row for row in rows),
            'TYPED_ROUTE_LEGS_INCOMPLETE')
    by_program = {row['binding']['program']: row for row in rows}
    require(set(by_program) == PROGRAMS, 'TYPED_ROUTE_FAMILY_DUPLICATE')
    m, s, o = (by_program[p]['binding'] for p in (METEORA, SABER, ORCA))
    require((m['input_mint'],m['output_mint']) == (WSOL,USDT)
            and (s['input_mint'],s['output_mint']) == (USDT,USDC)
            and (o['input_mint'],o['output_mint']) == (WSOL,USDC), 'TYPED_ROUTE_MINT_PATH')
    require(m['source'] == o['source'] == route_source
            and m['destination'] == s['source']
            and s['destination'] == o['destination'] == route_destination,
            'TYPED_ROUTE_ACCOUNT_PATH')
    require(by_program[METEORA]['ordinal'] < by_program[SABER]['ordinal']
            and by_program[METEORA]['children']['output_raw'] == str(s['amount_in']),
            'TYPED_INTERMEDIATE_AMOUNT_OR_ORDER')
    return {'status': 'TYPED_ROUTE_LINKS_MATCHED', 'execution_ready': False}
