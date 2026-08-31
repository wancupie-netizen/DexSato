"""E.2B read-only audit: unsigned evidence -> fresh simulation -> pool snapshot.

Fees must remain disabled. No signing, sendTransaction, execution or claim API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from application.jupiter_pool_validation import (
    PANCAKE, JUPITER, TOKEN, WSOL, BindingRejected, require, pancake_call,
    validate_pancake_snapshot, minimum_arithmetic, make_probe, probe_result,
)
from application.jupiter_typed_pool_binding import audit_typed_calls, validate_route_links


def audit(args):
    # Imports delayed so pure validation tests do not need HTTP or wallet SDKs.
    from application.jupiter_fee_simulation import (
        load_evidence, amount, inspect_resolved, verify_referral_accounts,
        validate_profile, simulate_rpc, summarize_simulation,
    )
    from application.jupiter_referral_verification import _rpc
    require(os.getenv('DEXSATO_JUPITER_FEE_ENABLED', 'false').strip().lower() == 'false', 'KEEP_FEES_DISABLED')
    require(1000000 <= amount(args.input_raw) <= 1000000000, 'INPUT_OUT_OF_BOUNDS')
    endpoint = os.getenv('SOLANA_RPC_URL', '')
    evidence = load_evidence(args.evidence)
    transaction = evidence['order']['transaction']
    resolved = inspect_resolved(transaction, endpoint)
    referral = os.getenv('DEXSATO_JUPITER_REFERRAL_ACCOUNT', '')
    obs = verify_referral_accounts(referral, os.getenv('DEXSATO_JUPITER_REFERRAL_PARTNER', ''), rpc_url=endpoint)
    fee_ata = dict(obs.token_accounts)[WSOL]
    profile = validate_profile(evidence, resolved, args.wallet, referral, fee_ata,
                               args.input_raw, args.minimum_output_raw, int(args.fee_bps))
    route = resolved['instructions'][profile['route_index']]
    minimum = minimum_arithmetic(route['args'], evidence['order'], amount(args.minimum_output_raw))
    slot = max(obs.slot, resolved['lookup_context']['slot'] or 0)
    result = simulate_rpc(endpoint, transaction, slot, [fee_ata, profile['destination']])
    summary = summarize_simulation(result, resolved, profile, args.wallet, referral, args.minimum_output_raw, slot)
    require(summary['simulation_succeeded'], 'BASELINE_SIMULATION_FAILED_REFRESH_EVIDENCE')
    require(summary['destination_net_meets_operator_minimum'], 'BASELINE_OUTPUT_BELOW_MINIMUM')
    require(int(summary['observed_destination_net_raw']) >= int(minimum['candidate_minimum_raw']), 'BASELINE_OUTPUT_BELOW_ORDER_MINIMUM')
    require(summary['observed_fee_in_raw'] == str(profile['gross_fee_arithmetic_raw'])
            and summary['observed_fee_out_raw'] == '0', 'BASELINE_FEE_MISMATCH')
    groups = [g for g in result['value']['innerInstructions'] if g['index'] == profile['route_index']]
    require(len(groups) == 1, 'ROUTE_CPI_GROUP_REQUIRED')
    inner = groups[0]['instructions']
    roles = route['accounts']; known = {a['address'] for a in resolved['accounts']}
    def fetch_typed(addresses, minimum_slot):
        return _rpc(endpoint, 'getMultipleAccounts', [addresses, {
            'encoding': 'base64', 'commitment': 'finalized', 'minContextSlot': minimum_slot}])
    typed, covered = audit_typed_calls(inner, known, roles['programAuthority']['address'],
                                      summary['simulation_slot'], fetch_typed)
    try:
        typed_links = validate_route_links(typed, roles['programSourceTokenAccount']['address'],
                                          roles['programDestinationTokenAccount']['address'])
    except BindingRejected as exc:
        typed_links = {'status': 'TYPED_ROUTE_LINKS_NOT_MATCHED', 'reason': str(exc), 'execution_ready': False}
    matches = []; unsupported = set()
    for ordinal, ix in enumerate(inner):
        if ordinal in covered:
            continue
        program = ix.get('programId')
        if program not in (PANCAKE, JUPITER, TOKEN):
            unsupported.add(program if isinstance(program, str) and program in known else 'UNRESOLVED_PROGRAM')
        if program != PANCAKE:
            continue
        call = pancake_call(ix); a = call['accounts']
        require(set(a).issubset(known), 'CPI_ACCOUNT_OUTSIDE_MESSAGE')
        require(a[0] == roles['programAuthority']['address']
                and a[3] == roles['programSourceTokenAccount']['address']
                and a[4] == roles['programDestinationTokenAccount']['address'], 'PANCAKE_JUPITER_ACCOUNT_BINDING')
        addresses = [a[2], a[5], a[6]]
        snapshot = _rpc(endpoint, 'getMultipleAccounts', [addresses, {
            'encoding': 'base64', 'commitment': 'finalized', 'minContextSlot': summary['simulation_slot']}])
        try:
            binding = validate_pancake_snapshot(ix, snapshot, addresses, summary['simulation_slot'])
        except BindingRejected as exc:
            binding = {'status': 'BINDING_NOT_MATCHED', 'reason': str(exc), 'execution_ready': False}
        matches.append({'call': call, 'binding': binding, 'snapshot_addresses': addresses,
                        'snapshot': snapshot})
    probe, mutation = make_probe(transaction, profile['route_index'])
    probe_rpc = simulate_rpc(endpoint, probe, summary['simulation_slot'], [fee_ata, profile['destination']])
    probe_summary = probe_result(probe_rpc, profile['route_index'], summary['simulation_slot'])
    return {'status': 'BINDING_REVIEW_REQUIRED', 'execution_ready': False, 'fee_receipt_verified': False,
            'message_sha256': resolved['message_sha256'], 'minimum_arithmetic': minimum,
            'negative_probe': {**probe_summary, 'mutation': mutation},
            'baseline_simulation': summary, 'referral_observation': obs.public_fields(),
            'pancake_bindings': matches, 'unsupported_pool_programs': sorted(unsupported),
            'typed_pool_bindings': typed,
            'typed_pool_binding_count': sum('binding' in item for item in typed),
            'typed_route_links': typed_links,
            'all_pool_bindings_verified': False,
            'blockers': (['TYPED_ROUTE_LINKS_REQUIRE_REVIEW'] if typed_links['status'] != 'TYPED_ROUTE_LINKS_MATCHED' else []) +
                        ['OTHER_POOL_FAMILIES_REQUIRE_TYPED_BINDING' if unsupported else 'FULL_CPI_SEMANTICS_NOT_PROVEN',
                         'PANCAKE_LAYOUT_IS_COMPATIBILITY_EVIDENCE_NOT_DEPLOYED_SOURCE_PROOF',
                         'MINIMUM_PROBE_IS_NOT_EXACT_BOUNDARY_OR_BYTECODE_PROOF',
                         'NO_ONCHAIN_FEE_RECEIPT'],
            'note': 'Current snapshots are later than simulation; no historical-state equivalence claimed.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence', 'output', 'wallet', 'input-raw', 'minimum-output-raw', 'fee-bps'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    try:
        require(not Path(args.output).exists(), 'OUTPUT_ALREADY_EXISTS')
        report = audit(args)
        with Path(args.output).open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
        print(json.dumps({'status': report['status'], 'execution_ready': False, 'fee_receipt_verified': False}))
        return 2  # Deliberately not deployment/transaction approval.
    except BindingRejected as exc:
        reason = str(exc)
    except Exception:
        reason = 'INPUT_DEPENDENCY_OR_UPSTREAM_VALIDATION_FAILED'
    print(json.dumps({'status': 'BINDING_AUDIT_INCOMPLETE', 'reason': reason, 'execution_ready': False}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
