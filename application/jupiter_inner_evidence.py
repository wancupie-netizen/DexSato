"""Lossless bounded CPI evidence and source-level claim arithmetic, never approval."""
import copy
import hashlib
import json

CLAIM_SOURCE = 'https://github.com/TeamRaccoons/referral/blob/6500f64ff004e78faa15d66446e175ede625260d/program/programs/referral/src/instructions/claim_v2.rs'


def capture_inner(value, top_level_count):
    groups = value.get('innerInstructions')
    if groups is None:
        return {'status': 'UNAVAILABLE', 'groups': [], 'instruction_count': 0}
    if not isinstance(groups, list) or len(groups) > 64:
        raise ValueError('INVALID_INNER_GROUPS')
    result = []; seen = set(); total = 0
    for group in groups:
        if not isinstance(group, dict) or type(group.get('index')) is not int or not 0 <= group['index'] < top_level_count or group['index'] in seen:
            raise ValueError('INVALID_INNER_GROUP_INDEX')
        seen.add(group['index'])
        instructions = group.get('instructions')
        if not isinstance(instructions, list) or len(instructions) > 512:
            raise ValueError('INVALID_INNER_INSTRUCTION_LIST')
        entries = []
        for ordinal, ix in enumerate(instructions):
            if not isinstance(ix, dict): raise ValueError('INVALID_INNER_INSTRUCTION')
            raw = json.dumps(ix, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            if len(raw) > 65536: raise ValueError('INNER_INSTRUCTION_TOO_LARGE')
            parsed = ix.get('parsed')
            form = 'RPC_PARSED' if isinstance(parsed, dict) else 'RPC_COMPILED' if 'programIdIndex' in ix else 'RPC_PARTIALLY_DECODED' if 'data' in ix else 'UNKNOWN'
            entries.append({'ordinal': ordinal, 'format': form,
                'program_id': ix.get('programId'), 'program_id_index': ix.get('programIdIndex'),
                'parsed_type': parsed.get('type') if isinstance(parsed, dict) else None,
                'stack_height': ix.get('stackHeight'), 'canonical_json_sha256': hashlib.sha256(raw).hexdigest(),
                'raw_instruction': copy.deepcopy(ix), 'semantics_verified': False})
        total += len(entries)
        result.append({'top_level_index': group['index'], 'instructions': entries})
    if total > 4096: raise ValueError('INNER_INSTRUCTION_TOTAL_LIMIT')
    return {'status': 'RECORDED_NOT_VERIFIED', 'groups': result, 'instruction_count': total,
        'note': 'Complete returned CPI objects, not raw transaction bytes for parsed instructions. No safety classification inferred.'}


def claim_projection(balance_raw, share_bps):
    if not isinstance(balance_raw, str) or not balance_raw.isascii() or not balance_raw.isdigit() or len(balance_raw) > 20 or str(int(balance_raw)) != balance_raw:
        raise ValueError('INVALID_CLAIM_BALANCE')
    balance = int(balance_raw)
    if balance >= 2**64 or type(share_bps) is not int or not 0 <= share_bps <= 10000:
        raise ValueError('INVALID_CLAIM_INPUT')
    partner = balance * share_bps // 10000
    return {'status': 'SOURCE_LEVEL_PROJECTION_ONLY', 'source': CLAIM_SOURCE,
        'basis': 'entire simulated post-fee-account balance, not incremental trade revenue',
        'balance_raw': balance_raw, 'partner_share_bps': share_bps,
        'partner_amount_raw': str(partner), 'project_amount_raw': str(balance-partner),
        'rounding': 'partner rounded down; project receives remainder',
        'distribution_time': 'claim_v2, not the swap deposit',
        'partner_destination': 'canonical ATA for referral_account.partner and mint',
        'project_destination': 'canonical ATA for project.admin and mint',
        'signing': 'payer signs; named referral PDA authorizes token transfers',
        'claim_executed': False, 'claim_simulated': False, 'deployed_bytecode_verified': False,
        'fee_receipt_verified': False, 'execution_ready': False}
