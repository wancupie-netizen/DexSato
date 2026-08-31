"""Operator-only unsigned boundary experiment. Never authorizes execution."""
import argparse
import base64
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from application.jupiter_pool_validation import (
    require, BindingRejected, JUPITER, b58encode, probe_result,
)


def matrix(output, slippage):
    require(type(output) is int and 1 < output < (2**64-1)//10000,
            'BOUNDARY_OUTPUT_RANGE')
    require(type(slippage) is int and 0 <= slippage <= 100, 'BOUNDARY_SLIPPAGE_RANGE')
    slip = slippage or 50  # Explicit synthetic rounding probe when original is zero.
    denominator = 10000-slip
    q = (output*10000 + denominator-1)//denominator
    if q*denominator % 10000 == 0:
        q += 1
    rows = [{'name': name, 'quoted': n, 'slippage': 0, 'expected': expected}
            for name,n,expected in [('below',output-1,'SUCCESS'),
                                    ('equal',output,'SUCCESS'),('above',output+1,'JUPITER_6001')]]
    require(q*denominator//10000 == output and q*denominator%10000,
            'ROUNDING_DISCRIMINATOR_UNAVAILABLE')
    upper=((output+1)*10000+denominator-1)//denominator
    for name,quote in [('rounding_lower',q-1),('rounding_split',q),('rounding_upper',upper)]:
        product=quote*denominator
        floor=product//10000;ceil=(product+9999)//10000
        rows.append({'name':name,'quoted':quote,'slippage':slip,'expected':'HYPOTHESIS',
                     'floor_minimum':floor,'ceil_minimum':ceil,
                     'floor_expected':'SUCCESS' if floor<=output else 'JUPITER_6001',
                     'ceil_expected':'SUCCESS' if ceil<=output else 'JUPITER_6001'})
    return rows


def mutate_unsigned(encoded, route_index, quoted, slippage):
    from application.jupiter_lookup_decoder import message_layout, MessageReader
    message_layout(encoded)
    require(type(quoted) is int and 0 < quoted <= (2**64-1)//10000
            and type(slippage) is int and 0 <= slippage <= 100, 'BOUNDARY_MUTATION_RANGE')
    raw=bytearray(base64.b64decode(encoded,validate=True)); r=MessageReader(bytes(raw))
    count=r.short();r.take(64*count)
    if raw[r.offset]&128: require(r.take(1)==b'\x80','BOUNDARY_VERSION')
    r.take(3);keys=[b58encode(r.take(32)) for _ in range(r.short())];r.take(32)
    n=r.short();require(type(route_index) is int and 0<=route_index<n,'BOUNDARY_ROUTE_INDEX')
    start=None
    for i in range(n):
        p=r.take(1)[0];r.take(r.short());size=r.short();offset=r.offset;data=r.take(size)
        if i==route_index:
            require(p<len(keys) and keys[p]==JUPITER and len(data)>=35
                    and data[:8].hex()=='d19853937cfed8e9','BOUNDARY_V2_ROUTE_REQUIRED')
            start=offset+17
    require(start is not None,'BOUNDARY_ROUTE_MISSING')
    before=bytes(raw)
    raw[start:start+8]=quoted.to_bytes(8,'little');raw[start+8:start+10]=slippage.to_bytes(2,'little')
    require(raw[:start]==before[:start] and raw[start+10:]==before[start+10:], 'BOUNDARY_UNEXPECTED_MUTATION')
    result=base64.b64encode(raw).decode();message_layout(result)
    return result


def pool_trace(result, route_index):
    """Fingerprint complete pool invocations/children, excluding Jupiter events.

    Failed minimum checks roll back state; pool CPI results before rejection
    are compared to the successful counterfactual, never treated as balances.
    """
    from application.jupiter_typed_pool_binding import PROGRAMS
    from application.jupiter_pool_validation import PANCAKE
    groups=result.get('value',{}).get('innerInstructions')
    require(isinstance(groups,list),'BOUNDARY_INNER_MISSING')
    found=[g for g in groups if g.get('index')==route_index]
    require(len(found)==1 and isinstance(found[0].get('instructions'),list),'BOUNDARY_ROUTE_GROUP')
    selected=[];active=False;calls=0
    for ix in found[0]['instructions']:
        require(isinstance(ix,dict) and type(ix.get('stackHeight')) is int,'BOUNDARY_CPI_DEPTH')
        if ix['stackHeight']==2:
            active=ix.get('programId') in PROGRAMS|{PANCAKE}
            calls+=int(active)
        if active:selected.append(ix)
    require(calls==4 and len(selected)<=128,'BOUNDARY_POOL_PROFILE')
    return hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def classify(calibration, rows, expected_matrix):
    require(type(calibration.get('output')) is int and calibration['output']>1
            and type(calibration.get('slot')) is int and calibration['slot']>=0,
            'BOUNDARY_CALIBRATION_REQUIRED')
    require(len(expected_matrix)==6 and len(rows)==6,'BOUNDARY_RESULT_COUNT')
    # Reconstruct all predictions instead of trusting report-supplied hypotheses.
    canonical=matrix(calibration['output'],expected_matrix[3]['slippage'])
    require(expected_matrix==canonical,'BOUNDARY_MATRIX_REQUIRED')
    output=calibration['output'];anchor=rows[1]
    slot=anchor.get('slot');trace=anchor.get('pool_trace')
    shared=[]
    if type(slot) is not int or slot<calibration['slot'] or not isinstance(trace,str) or len(trace)!=64:
        shared.append('INVALID_COMPARISON_BANK')
    if anchor.get('outcome')!='SUCCESS' or anchor.get('output')!=output:
        shared.append('EQUALITY_REFERENCE_NOT_CONFIRMED')

    def reasons_for(row,spec):
        reasons=[]
        if any(type(row.get(k)) is not type(v) or row.get(k)!=v for k,v in spec.items()):
            reasons.append('PROBE_SPECIFICATION_MISMATCH')
        if type(row.get('slot')) is not int or row['slot']!=slot:reasons.append('FINALIZED_BANK_SLOT_CHANGED')
        if row.get('pool_trace')!=trace:reasons.append('POOL_CPI_TRACE_CHANGED')
        outcome=row.get('outcome')
        if outcome not in ('SUCCESS','JUPITER_6001'):reasons.append('UNCLASSIFIED_PROBE_FAILURE')
        # Failure has no committed balance; never label its nulls as fee changes.
        if outcome=='SUCCESS':
            if type(row.get('output')) is not int or row['output']!=output:reasons.append('SUCCESS_OUTPUT_CHANGED_OR_MISSING')
            if row.get('fee')!=calibration['fee']:reasons.append('SUCCESS_FEE_CHANGED_OR_MISSING')
        elif row.get('output') is not None or row.get('fee') is not None:
            reasons.append('FAILED_PROBE_HAS_BALANCE_CLAIM')
        return reasons

    boundary_reasons=list(shared);rounding_reasons=list(shared);diagnostics=[]
    for i,(row,spec) in enumerate(zip(rows,canonical)):
        reasons=reasons_for(row,spec)
        if i<3 and row.get('outcome')!=spec['expected']:reasons.append('UNEXPECTED_BOUNDARY_OUTCOME')
        diagnostics.append({'name':spec['name'],'outcome':row.get('outcome'),'reasons':sorted(set(reasons))})
        (boundary_reasons if i<3 else rounding_reasons).extend(reasons)
    boundary=not boundary_reasons
    if not boundary:rounding_reasons.append('BOUNDARY_REFERENCE_NOT_ESTABLISHED')
    hypotheses={}
    for name in ('floor','ceil'):
        mismatches=[spec['name'] for row,spec in zip(rows[3:],canonical[3:])
                    if row.get('outcome')!=spec[name+'_expected']]
        hypotheses[name]={'status':'INCONCLUSIVE' if rounding_reasons else
                          ('CONSISTENT_WITH_SAMPLES' if not mismatches else 'CONTRADICTED_BY_SAMPLES'),
                          'mismatching_probes':mismatches}
    winner=[name for name,h in hypotheses.items() if h['status']=='CONSISTENT_WITH_SAMPLES']
    conclusion=winner[0].upper()+'_CONSISTENT_WITH_SAMPLES' if len(winner)==1 else 'ROUNDING_INCONCLUSIVE'
    return {'schema_version':'E2D1','status':'BOUNDARY_ROUNDING_REVIEW_REQUIRED',
            'comparison_slot':slot,'boundary_observed':boundary,
            'boundary':{'status':'SAME_BANK_BOUNDARY_OBSERVED' if boundary else 'BOUNDARY_INCONCLUSIVE',
                        'reasons':sorted(set(boundary_reasons))},
            'rounding':{'status':conclusion,'hypotheses':hypotheses,'reasons':sorted(set(rounding_reasons))},
            'probe_diagnostics':diagnostics,'execution_ready':False,'fee_receipt_verified':False,
            'general_enforcement_proven':False,'production_formula_changed':False,
            'note':'Separate finite boundary/rounding observations, conditional on RPC bank/trace reporting. No universal formula or execution approval.'}


def audit_boundary(args):
    from application.jupiter_binding_audit import audit
    from application.jupiter_fee_simulation import load_evidence, inspect_resolved, simulate_rpc, summarize_simulation
    require(os.getenv('DEXSATO_JUPITER_FEE_ENABLED','false').strip().lower()=='false','KEEP_FEES_DISABLED')
    prior=audit(args)  # Fresh E.2C preflight, including referral and byte/intent checks.
    require(prior['typed_pool_binding_count']==3 and not prior['unsupported_pool_programs']
            and prior['typed_route_links']['status']=='TYPED_ROUTE_LINKS_MATCHED'
            and len(prior['pancake_bindings'])==1
            and prior['pancake_bindings'][0]['binding']['status']=='CANDIDATE_LAYOUT_BINDING_MATCHED',
            'BOUNDARY_POOL_PREFLIGHT_INCOMPLETE')
    endpoint=os.getenv('SOLANA_RPC_URL',''); evidence=load_evidence(args.evidence)
    tx=evidence['order']['transaction'];resolved=inspect_resolved(tx,endpoint)
    require(resolved['message_sha256']==prior['message_sha256'],'BOUNDARY_EVIDENCE_CHANGED')
    profile=prior['baseline_simulation']['profile'];idx=profile['route_index']
    addresses=[profile['fee_ata'],profile['destination']]
    referral=os.getenv('DEXSATO_JUPITER_REFERRAL_ACCOUNT','')
    minimum_slot=max(prior['negative_probe']['probe_slot'],resolved['lookup_context']['slot'] or 0)
    raw=simulate_rpc(endpoint,tx,minimum_slot,addresses)
    summary=summarize_simulation(raw,resolved,profile,args.wallet,referral,args.minimum_output_raw,minimum_slot)
    require(summary['simulation_succeeded'] and summary['destination_net_meets_operator_minimum']
            and summary['observed_fee_in_raw']==str(profile['gross_fee_arithmetic_raw'])
            and summary['observed_fee_out_raw']=='0','BOUNDARY_CALIBRATION_FAILED')
    calibration={'slot':summary['simulation_slot'],'output':int(summary['observed_destination_net_raw']),
                 'fee':summary['observed_fee_in_raw'],'pool_trace':pool_trace(raw,idx)}
    require(calibration['output']>=int(prior['minimum_arithmetic']['candidate_minimum_raw']),
            'BOUNDARY_CALIBRATION_BELOW_ORDER_MINIMUM')
    specs=matrix(calibration['output'],resolved['instructions'][idx]['args']['slippageBps'])
    def run(spec):
        mutated=mutate_unsigned(tx,idx,spec['quoted'],spec['slippage'])
        result=simulate_rpc(endpoint,mutated,calibration['slot'],addresses)
        probe=probe_result(result,idx,calibration['slot'])
        row={**spec,'slot':result['context']['slot'],'pool_trace':pool_trace(result,idx),
             'transaction_sha256':hashlib.sha256(base64.b64decode(mutated)).hexdigest(),
             'outcome':'OTHER_FAILURE','output':None,'fee':None}
        if result['value']['err'] is None:
            s=summarize_simulation(result,resolved,profile,args.wallet,referral,'1',calibration['slot'])
            require(s['observed_fee_out_raw']=='0','BOUNDARY_FEE_OUTFLOW')
            row.update(outcome='SUCCESS',output=int(s['observed_destination_net_raw']),fee=s['observed_fee_in_raw'])
        elif probe['jupiter_slippage_rejection_observed']:
            row['outcome']='JUPITER_6001'
        return row
    def safe_run(spec):
        try:
            return run(spec)
        except Exception:
            # One failed RPC/invalid trace must not erase other probe evidence.
            # Never expose exception text, endpoint credentials or raw payloads.
            return {**spec,'slot':None,'pool_trace':None,'outcome':'OTHER_FAILURE',
                    'output':None,'fee':None,'reason':'PROBE_UPSTREAM_OR_EVIDENCE_UNAVAILABLE'}
    # Bounded parallel read-only probes; no automatic retries and no exact-slot
    # claim from minContextSlot alone. Actual returned slots MUST all match.
    with ThreadPoolExecutor(max_workers=6) as executor:
        rows=list(executor.map(safe_run,specs))
    return {**classify(calibration,rows,specs),'message_sha256':resolved['message_sha256'],
            'calibration':calibration,'probes':rows,'preflight':prior,
            'remaining_blockers':['FULL_CPI_SEMANTICS_NOT_PROVEN','DEPLOYED_SOURCE_EQUIVALENCE_NOT_PROVEN',
                                  'FINITE_BOUNDARY_SAMPLES_ONLY','NO_ONCHAIN_FEE_RECEIPT']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','output','wallet','input-raw','minimum-output-raw','fee-bps'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    try:
        require(not Path(args.output).exists(),'OUTPUT_ALREADY_EXISTS')
        report=audit_boundary(args)
        with Path(args.output).open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2,allow_nan=False)
        print(json.dumps({k:report[k] for k in ('status','execution_ready','fee_receipt_verified')}))
        return 2
    except BindingRejected as exc:
        reason=str(exc)
    except Exception:
        reason='BOUNDARY_INPUT_OR_UPSTREAM_UNAVAILABLE'
    print(json.dumps({'status':'BOUNDARY_AUDIT_INCOMPLETE','reason':reason,'execution_ready':False}))
    return 1


if __name__=='__main__':raise SystemExit(main())
