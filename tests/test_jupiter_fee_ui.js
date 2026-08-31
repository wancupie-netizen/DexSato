/* node --test tests/test_jupiter_fee_ui.js — mocked DOM/wallet; no network. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(bps = 0) {
    return {output_mint:'TOKEN', input_amount_sol:'0.1', input_amount_lamports:'100000000',
        output_amount_ui:'2.5', output_decimals:6, minimum_received_ui:'2.4',
        dexsato_integrator_fee_bps:bps, dexsato_fee_policy_id:'a'.repeat(64),
        dexsato_referral_account:bps ? '5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ' : null,
        dexsato_fee_mint:bps ? 'So11111111111111111111111111111111111111112' : null,
        fee_disclosure:{version:1, policy_id:'a'.repeat(64), integrator_fee_bps:bps,
            integrator_fee_percent:(bps/100).toFixed(2), integrator_fee_amount_ui:bps?'0.0005':'0',
            integrator_fee_symbol:bps?'WSOL':'SOL', amount_kind:bps?'ESTIMATE':'ZERO',
            referral_verification:bps?'RPC_ACCOUNT_VERIFIED':'NOT_REQUIRED',
            execution_ready:!bps, jupiter_share_percent:'20.00',
            note:'Estimate only. No fee receipt verified.', network_fee_note:'Network fees separate.'}};
}

function boot(payload = fixture()) {
    class Element {
        constructor() {this.children=[];this.events={};this.value='0.1';this.checked=false;this.disabled=false;
            this.dataset={tokenAddress:'TOKEN',tokenSymbol:'TEST'};this.classList={add(){},remove(){}};}
        append(...items){this.children.push(...items);}
        appendChild(item){this.children.push(item);}
        replaceChildren(){this.children=[];}
        addEventListener(name,cb){this.events[name]=cb;}
        focus(){} select(){}
    }
    const elements = new Map();
    const el = selector => {if(!elements.has(selector))elements.set(selector,new Element());return elements.get(selector);};
    el('[data-jupiter-sandbox]').querySelector=el;
    const document={querySelector:el,querySelectorAll:()=>[],createElement:()=>new Element(),head:new Element()};
    let signed=0, prepared=0;
    const wallet={publicKey:'WALLET', connect:async()=>({publicKey:'WALLET'}),on(){},
        signTransaction:async()=>{signed++;return {serialize:()=>new Uint8Array([1])};}};
    const context={document,console,Intl,Uint8Array,Date,Number,Promise,
        window:{solana:wallet,phantom:{solana:wallet},setTimeout,
            atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64'),
            solanaWeb3:{VersionedTransaction:{deserialize:()=>({})}}},
        fetch:async url=>({ok:true,json:async()=>{
            if(url.includes('jupiter-order')){prepared++;return {...payload, output_amount_ui:'2.3',
                wallet_address:'WALLET',unsigned_transaction:'AQ==',request_id:'order',expires_at:new Date(Date.now()+60000).toISOString()};}
            if(url.includes('jupiter-execute'))return {status:'SWAP_CONFIRMED',signature:'test'};
            return payload;
        }})};
    const source=fs.readFileSync(path.join(__dirname,'../static/js/dexsato_solana_discovery_swap.js'),'utf8');
    vm.runInNewContext(source.replace(/\}\)\(\);\s*$/, 'globalThis.helpers={validFeeDisclosure,sameFeePolicy,renderFeeDisclosure};})();'),context);
    return {context,el,counts:()=>({signed,prepared}),click:selector=>el(selector).events.click()};
}

test('zero-fee and verified fee-preview contracts accepted; malformed data rejected',()=>{
    const {context}=boot();
    assert.equal(context.helpers.validFeeDisclosure(fixture()),true);
    assert.equal(context.helpers.validFeeDisclosure(fixture(50)),true);
    for(const change of [{policy_id:'wrong'},{integrator_fee_bps:'50'},{integrator_fee_amount_ui:null},
        {integrator_fee_percent:'0.10'},{referral_verification:'PROVIDER_VALIDATED'},{execution_ready:true}]){
        const value=fixture(50);Object.assign(value.fee_disclosure,change);
        assert.equal(context.helpers.validFeeDisclosure(value),false);
    }
});

test('policy/account/mint mismatch rejected',()=>{
    const {context}=boot(), first=fixture();
    assert.equal(context.helpers.sameFeePolicy(first,fixture()),true);
    const second=fixture();second.dexsato_fee_policy_id='b'.repeat(64);
    assert.equal(context.helpers.sameFeePolicy(first,second),false);
    assert.equal(context.helpers.sameFeePolicy(first,fixture(50)),false);
});

test('disclosure renders text only and includes network/estimate note',()=>{
    const {context,el}=boot(), target=el('test'), value=fixture(50);
    value.fee_disclosure.note='<img src=x onerror=alert(1)>';
    context.helpers.renderFeeDisclosure(target,value);
    assert.ok(target.children.some(x=>x.textContent?.includes('<img')));
    assert.ok(target.children.some(x=>x.children?.some(y=>y.textContent==='Jupiter share (included)')));
});

test('fee-enabled preview cannot prepare or sign',async()=>{
    const b=boot(fixture(50));
    await b.click('[data-connect-wallet]');await b.click('[data-get-quote]');
    b.el('[data-swap-risk-ack]').checked=true;b.el('[data-swap-risk-ack]').events.change();
    assert.equal(b.el('[data-execute-swap]').disabled,true);
    assert.deepEqual(b.counts(),{signed:0,prepared:0});
});

test('actual prepared order must be reviewed on a separate click before signing',async()=>{
    const b=boot();
    await b.click('[data-connect-wallet]');await b.click('[data-get-quote]');
    b.el('[data-swap-risk-ack]').checked=true;b.el('[data-swap-risk-ack]').events.change();
    await b.click('[data-execute-swap]'); // quote summary
    await b.click('[data-execute-swap]'); // prepare + actual order summary
    assert.deepEqual(b.counts(),{signed:0,prepared:1});
    assert.ok(JSON.stringify(b.el('[data-confirmation-summary]').children).includes('2.3'));
    await b.click('[data-execute-swap]');
    assert.deepEqual(b.counts(),{signed:1,prepared:1});
});

test('amount change discards prepared order and prevents signing',async()=>{
    const b=boot();
    await b.click('[data-connect-wallet]');await b.click('[data-get-quote]');
    b.el('[data-swap-risk-ack]').checked=true;
    await b.click('[data-execute-swap]');await b.click('[data-execute-swap]');
    b.el('[data-quote-amount]').value='0.2';b.el('[data-quote-amount]').events.input();
    await b.click('[data-execute-swap]');
    assert.equal(b.counts().signed,0);
});
