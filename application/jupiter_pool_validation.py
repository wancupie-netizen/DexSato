"""Read-only E.2B evidence checks. Never an execution authorization.

Pancake uses a Raydium-family *candidate* layout. Matching bytes and PDAs do
not prove deployed bytecode semantics. Other pool families remain unreviewed.
"""
import base64
import hashlib
import re

PANCAKE = 'HpNfyc2Saw7RKkQd8nEL4khUcuPhQ7WwY1B2qjx8jxFq'
JUPITER = 'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4'
TOKEN = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
WSOL = 'So11111111111111111111111111111111111111112'
USDC = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
IDENTITY_SOURCE = 'https://github.com/pancakeswap/pancakeswap-ai/blob/f8d2f9da32b9a12404e921fab900648d056853a8/packages/plugins/pancakeswap-driver/skills/collect-fees/references/fetch-solana.cjs'
LAYOUT_SOURCE = 'https://github.com/raydium-io/raydium-clmm/blob/ed7c84a54ced59c55981780546adb0b4583dcf85/programs/amm/src/states/pool.rs'
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


class BindingRejected(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise BindingRejected(code)


def b58decode(text, limit=4096):
    require(isinstance(text, str) and 0 < len(text) <= limit, 'INVALID_BASE58')
    number = 0
    for c in text:
        require(c in ALPHABET, 'INVALID_BASE58')
        number = number * 58 + ALPHABET.index(c)
    return bytes(len(text) - len(text.lstrip('1'))) + number.to_bytes((number.bit_length()+7)//8, 'big')


def b58encode(raw):
    n = int.from_bytes(raw, 'big'); out = ''
    while n:
        n, r = divmod(n, 58); out = ALPHABET[r] + out
    return '1' * (len(raw)-len(raw.lstrip(b'\0'))) + out


def key(text):
    raw = b58decode(text, 44)
    require(len(raw) == 32, 'INVALID_PUBLIC_KEY')
    return raw


def uint(value):
    require(type(value) is int and 0 <= value < 2**64, 'INVALID_U64')
    return value


def raw_account(account, owner, size=None):
    require(isinstance(account, dict) and account.get('owner') == owner
            and account.get('executable') is False, 'ACCOUNT_OWNER_OR_EXECUTABLE_MISMATCH')
    data = account.get('data')
    require(isinstance(data, list) and len(data) == 2 and data[1] == 'base64'
            and isinstance(data[0], str) and len(data[0]) <= 20000, 'ACCOUNT_ENCODING')
    try:
        raw = base64.b64decode(data[0], validate=True)
    except (ValueError, TypeError):
        raise BindingRejected('ACCOUNT_ENCODING') from None
    require(base64.b64encode(raw).decode() == data[0], 'ACCOUNT_ENCODING')
    require(len(raw) == size if size is not None else 8 <= len(raw) <= 15000, 'ACCOUNT_SIZE')
    return raw


def token_vault(account, mint, authority):
    raw = raw_account(account, TOKEN, 165)
    require(raw[:32] == key(mint) and raw[32:64] == key(authority), 'VAULT_MINT_OR_AUTHORITY')
    require(raw[108] == 1 and raw[72:76] == bytes(4) and raw[129:133] == bytes(4)
            and raw[121:129] == bytes(8), 'VAULT_STATE_OR_DELEGATE')
    require(int.from_bytes(raw[109:113], 'little') == (1 if mint == WSOL else 0), 'VAULT_NATIVE_STATE')
    return {'mint': mint, 'authority': authority, 'amount_raw': str(int.from_bytes(raw[64:72], 'little')),
            'data_sha256': hashlib.sha256(raw).hexdigest()}


def pancake_call(ix):
    require(isinstance(ix, dict) and ix.get('programId') == PANCAKE and ix.get('stackHeight') == 2, 'PANCAKE_CPI_REQUIRED')
    accounts = ix.get('accounts')
    require(isinstance(accounts, list) and 10 <= len(accounts) <= 32, 'PANCAKE_ACCOUNT_COUNT')
    for address in accounts:
        key(address)
    require(len(set(accounts)) == len(accounts) and accounts[8] == TOKEN, 'PANCAKE_ACCOUNT_ALIAS_OR_TOKEN_PROGRAM')
    data = b58decode(ix.get('data'))
    require(len(data) == 41 and data[:8] == hashlib.sha256(b'global:swap').digest()[:8], 'PANCAKE_SWAP_ENCODING')
    require(data[40] == 1 and int.from_bytes(data[8:16], 'little') > 0, 'PANCAKE_EXACT_INPUT_REQUIRED')
    return {'accounts': accounts, 'input_raw': int.from_bytes(data[8:16], 'little'),
            'leg_minimum_raw': int.from_bytes(data[16:24], 'little'),
            'sqrt_price_limit': str(int.from_bytes(data[24:40], 'little'))}


def pda(seeds, program):
    from solders.pubkey import Pubkey
    return str(Pubkey.find_program_address(seeds, Pubkey.from_string(program))[0])


def validate_pancake_snapshot(ix, snapshot, addresses, minimum_slot):
    call = pancake_call(ix); a = call['accounts']
    expected = [a[2], a[5], a[6]]
    require(addresses == expected and len(set(addresses)) == 3, 'SNAPSHOT_ADDRESS_BINDING')
    require(isinstance(snapshot, dict) and isinstance(snapshot.get('context'), dict), 'SNAPSHOT_ENVELOPE')
    slot = snapshot['context'].get('slot')
    require(type(minimum_slot) is int and minimum_slot >= 0 and type(slot) is int and slot >= minimum_slot, 'STALE_SNAPSHOT')
    values = snapshot.get('value')
    require(isinstance(values, list) and len(values) == 3, 'SNAPSHOT_ACCOUNT_COUNT')
    raw = raw_account(values[0], PANCAKE)
    require(len(raw) >= 233 and raw[:8] == hashlib.sha256(b'account:PoolState').digest()[:8], 'POOL_LAYOUT')
    config, mint0, mint1 = b58encode(raw[9:41]), b58encode(raw[73:105]), b58encode(raw[105:137])
    vault0, vault1, observation = b58encode(raw[137:169]), b58encode(raw[169:201]), b58encode(raw[201:233])
    require(config == a[1] and observation == a[7], 'POOL_CONFIG_OR_OBSERVATION_BINDING')
    require({mint0, mint1} == {WSOL, USDC} and key(mint0) < key(mint1), 'POOL_MINT_PAIR')
    require(a[2] == pda([b'pool', key(config), key(mint0), key(mint1)], PANCAKE), 'POOL_PDA_BINDING')
    pair = {mint0: vault0, mint1: vault1}
    require(pair[WSOL] == a[5] and pair[USDC] == a[6], 'POOL_VAULT_DIRECTION_BINDING')
    for mint, vault in pair.items():
        require(vault == pda([b'pool_vault', key(a[2]), key(mint)], PANCAKE), 'VAULT_PDA_BINDING')
    return {'status': 'CANDIDATE_LAYOUT_BINDING_MATCHED', 'program_id': PANCAKE,
            'identity_source': IDENTITY_SOURCE, 'layout_source': LAYOUT_SOURCE,
            'layout_authority': 'RAYDIUM_FAMILY_NOT_PANCAKE_BYTECODE_PROOF',
            'snapshot_slot': slot, 'pool': a[2], 'pool_data_sha256': hashlib.sha256(raw).hexdigest(),
            'input_vault': token_vault(values[1], WSOL, a[2]),
            'output_vault': token_vault(values[2], USDC, a[2]),
            'execution_ready': False, 'deployed_bytecode_verified': False}


def minimum_arithmetic(args, order, operator_minimum):
    quoted = uint(args['quotedOutAmount']); slip = args['slippageBps']
    require(type(slip) is int and 0 <= slip <= 10000, 'INVALID_SLIPPAGE')
    require(isinstance(order.get('outAmount'), str) and order['outAmount'] == str(quoted)
            and type(order.get('slippageBps')) is int and order['slippageBps'] == slip, 'ORDER_MINIMUM_HEADER_MISMATCH')
    expected = quoted * (10000-slip) // 10000
    require(isinstance(order.get('otherAmountThreshold'), str) and order['otherAmountThreshold'] == str(expected)
            and 0 < uint(operator_minimum) <= expected, 'ORDER_MINIMUM_ARITHMETIC_MISMATCH')
    return {'candidate_minimum_raw': str(expected), 'operator_minimum_raw': str(operator_minimum),
            'formula': 'floor(quotedOutAmount * (10000 - slippageBps) / 10000)',
            'status': 'ARITHMETIC_MATCH_ONLY', 'enforcement_verified': False}


def make_probe(encoded, route_index):
    """Modify only quotedOutAmount/slippage of one unsigned static-Jupiter V2 ix.

    Probe transaction is kept in memory, never returned by CLI or written to disk.
    """
    from application.jupiter_lookup_decoder import message_layout, MessageReader
    message_layout(encoded)  # Existing bounded parser rejects any signature.
    raw = bytearray(base64.b64decode(encoded, validate=True))
    r = MessageReader(bytes(raw)); count = r.short(); r.take(64*count)
    if raw[r.offset] & 128:
        require(r.take(1) == b'\x80', 'PROBE_VERSION')
    r.take(3); keys = [b58encode(r.take(32)) for _ in range(r.short())]; r.take(32)
    n = r.short(); require(type(route_index) is int and 0 <= route_index < n, 'PROBE_ROUTE_INDEX')
    found = None
    for index in range(n):
        program_index = r.take(1)[0]; r.take(r.short()); size = r.short(); offset = r.offset; data = r.take(size)
        if index == route_index:
            require(program_index < len(keys) and keys[program_index] == JUPITER
                    and len(data) >= 35 and data[:8].hex() == 'd19853937cfed8e9', 'PROBE_JUPITER_V2_REQUIRED')
            quoted = int.from_bytes(data[17:25], 'little')
            high = max(10**12, quoted*2+1)
            require(high <= (2**64-1)//10000, 'PROBE_AMOUNT_BOUND')
            found = (offset+17, high)
    require(found is not None, 'PROBE_ROUTE_MISSING')
    start, high = found
    raw[start:start+8] = high.to_bytes(8, 'little'); raw[start+8:start+10] = bytes(2)
    mutated = base64.b64encode(raw).decode(); message_layout(mutated)
    return mutated, {'quoted_output_raw': str(high), 'slippage_bps': 0,
                     'changed_fields': ['quotedOutAmount', 'slippageBps'], 'execution_ready': False}


def probe_diagnostics(value, route_index):
    """Allowlisted structured diagnostics only; never persist provider prose.

    Missing/unrecognized information remains explicit. Diagnostic fields do not
    participate in authorization or make an inconclusive probe pass.
    """
    err = value.get('err')
    error = {'kind': 'NONE' if err is None else 'UNRECOGNIZED'}
    enums = {'InvalidArgument', 'InvalidInstructionData', 'InvalidAccountData',
             'AccountDataTooSmall', 'InsufficientFunds', 'IncorrectProgramId',
             'MissingRequiredSignature', 'ComputationalBudgetExceeded',
             'ProgramFailedToComplete', 'ProgramFailedToCompile',
             'InvalidError', 'ArithmeticOverflow', 'InvalidSeeds'}
    if isinstance(err, dict) and set(err) == {'InstructionError'}:
        entry = err['InstructionError']
        if isinstance(entry, list) and len(entry) == 2 and type(entry[0]) is int and 0 <= entry[0] <= 255:
            error = {'kind': 'INSTRUCTION_ERROR', 'instruction_index': entry[0],
                     'at_expected_route': entry[0] == route_index, 'detail': 'UNRECOGNIZED'}
            detail = entry[1]
            if isinstance(detail, dict) and set(detail) == {'Custom'} and type(detail['Custom']) is int and 0 <= detail['Custom'] < 2**32:
                error.update(detail='CUSTOM', custom_code=detail['Custom'])
            elif isinstance(detail, str) and detail in enums:
                error['detail'] = detail
    elif isinstance(err, str) and err in {'BlockhashNotFound', 'AccountNotFound', 'InsufficientFundsForFee', 'InvalidAccountForFee', 'AlreadyProcessed'}:
        error = {'kind': 'TRANSACTION_ERROR', 'detail': err}
    logs = value.get('logs')
    require(logs is None or (isinstance(logs, list) and len(logs) <= 4096
            and all(isinstance(x, str) and len(x) <= 8192 for x in logs)), 'PROBE_LOGS')
    events = []; omitted = 0; limit = 128
    for index, line in enumerate(logs or []):
        event = None
        m = re.fullmatch(r'Program ([1-9A-HJ-NP-Za-km-z]{32,44}) (invoke \[([0-9]{1,2})\]|success|failed: custom program error: (0x[0-9a-fA-F]{1,8})|failed: (.+))', line)
        if m:
            try:
                key(m[1])
            except BindingRejected:
                m = None
        if m:
            event = {'line_index': index, 'program_id': m[1],
                     'event': 'INVOKE' if m[3] else 'SUCCESS' if m[2] == 'success' else 'FAILED'}
            if m[3]: event['stack_height'] = int(m[3])
            if m[4]: event['custom_code'] = int(m[4], 16)
            if m[5]: event['detail'] = {'Computational budget exceeded': 'COMPUTE_EXCEEDED', 'Program failed to complete': 'PROGRAM_FAILED_TO_COMPLETE'}.get(m[5], 'REDACTED_UNRECOGNIZED_DETAIL')
        elif line.startswith('Program log: AnchorError'):
            number = re.search(r'Error Number: ([0-9]{1,10})\.', line)
            label = re.search(r'Error Code: (SlippageToleranceExceeded|InsufficientFunds|InvalidTokenAccount|InvalidCalculation)\.', line)
            if number and int(number[1]) < 2**32 or label:
                event = {'line_index': index, 'event': 'ANCHOR_ERROR'}
                if number and int(number[1]) < 2**32: event['error_number'] = int(number[1])
                if label: event['error_code'] = label[1]
        if event is not None and len(events) < limit:
            events.append(event)
        else:
            omitted += 1
    return {'error': error, 'logs_available': logs is not None,
            'log_line_count': len(logs or []), 'filtered_events': events,
            'omitted_line_count': omitted, 'event_limit_reached': len(events) == limit,
            'raw_logs_saved': False, 'execution_ready': False}


def jupiter_rejection_trace(logs, route_index):
    """Recognize a complete runtime invocation stack, not an Anchor prose line."""
    stack = []; top_index = -1; rejected = False
    if not logs or type(route_index) is not int or not 0 <= route_index < 64:
        return False
    for line in logs:
        if 'log truncated' in line.lower():
            return False
        invoke = re.fullmatch(r'Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]?)\]', line)
        finish = re.fullmatch(r'Program ([1-9A-HJ-NP-Za-km-z]{32,44}) (success|failed: (.+))', line)
        if invoke or finish:
            m = invoke or finish
            try:
                key(m[1])
            except BindingRejected:
                return False
            if rejected:
                return False
            if invoke:
                if int(invoke[2]) != len(stack)+1:
                    return False
                if not stack:
                    top_index += 1
                stack.append(invoke[1])
            else:
                if not stack or stack[-1] != finish[1]:
                    return False
                if finish[2] != 'success':
                    if (len(stack) != 1 or finish[1] != JUPITER or top_index != route_index
                            or finish[3] != 'custom program error: 0x1771'):
                        return False
                    rejected = True
                stack.pop()
        elif line.startswith('Program ') and not line.startswith(('Program log:', 'Program data:', 'Program return:')):
            # Compute consumption is harmless; malformed lifecycle is not.
            if any(word in line for word in ('invoke', 'success', 'failed:')):
                return False
    return rejected and not stack and top_index == route_index


def probe_result(result, route_index, minimum_slot):
    require(isinstance(result, dict) and isinstance(result.get('context'), dict)
            and isinstance(result.get('value'), dict), 'PROBE_RESPONSE')
    slot = result['context'].get('slot')
    require(type(slot) is int and slot >= minimum_slot, 'PROBE_SLOT')
    v = result['value']
    diagnostics = probe_diagnostics(v, route_index)
    logs = v.get('logs') or []
    error = diagnostics['error']
    matched = (error.get('kind') == 'INSTRUCTION_ERROR'
               and error.get('instruction_index') == route_index
               and error.get('custom_code') == 6001
               and jupiter_rejection_trace(logs, route_index))
    return {'status': 'NEGATIVE_MINIMUM_PROBE_OBSERVED' if matched else 'MINIMUM_PROBE_INCONCLUSIVE',
            'probe_slot': slot, 'jupiter_slippage_rejection_observed': matched,
            'diagnostics': diagnostics,
            'classification_basis': 'PROGRAM_INDEX_CODE_AND_COMPLETE_RUNTIME_TRACE',
            'error_mapping_source': 'https://developers.jup.ag/docs/swap/v1/common-errors',
            'enforcement_verified': False, 'execution_ready': False,
            'note': 'Different-slot unsigned probe; not bytecode proof, exact rounding proof or execution approval.'}
