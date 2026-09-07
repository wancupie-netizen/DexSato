"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const api = require("../tools/claim_v2_sign_only/sign-only.js");

const messageHash = "a".repeat(64);
const transactionHash = "b".repeat(64);
function artifacts(overrides = {}) {
  const capture = {
    status: "SDK_UNSIGNED_CAPTURED", execution_ready: false,
    fee_receipt_verified: false, message_sha256: messageHash,
    transaction_sha256: transactionHash, transaction: "AQ==",
    identity: { payer: "wallet", partner: "wallet", referral_account: "referral", mint: "mint" },
  };
  const gate = {
    status: "ARMED", gate_id: "gate", message_sha256: messageHash,
    unsigned_transaction_sha256: transactionHash, partner: "wallet",
    referral_account: "referral", mint: "mint", exact_claim_raw: "5000",
    expected_partner_raw: "4000", expected_project_raw: "1000",
    approval_count: 0, submission_attempt_count: 0, wallet_review_count: 0,
    live_claim_approved: false, claim_submitted: false, execution_ready: false,
    expires_at: new Date(Date.now() + 60000).toISOString(),
  };
  Object.assign(gate, overrides);
  return { capture, gate };
}

test("exact fresh artifacts are accepted for sign-only review", () => {
  const { capture, gate } = artifacts();
  assert.deepEqual(api.validateArtifacts(capture, gate), { wallet: "wallet", gateId: "gate" });
});

test("amount, hash, identity and used-gate mutations fail closed", () => {
  for (const change of [
    { exact_claim_raw: "5001" }, { message_sha256: "c".repeat(64) },
    { partner: "other" }, { approval_count: 1 }, { submission_attempt_count: 1 },
    { live_claim_approved: true }, { claim_submitted: true },
  ]) {
    const { capture, gate } = artifacts(change);
    assert.throws(() => api.validateArtifacts(capture, gate));
  }
});

test("expired gate is rejected", () => {
  const { capture, gate } = artifacts({ expires_at: new Date(Date.now() - 1).toISOString() });
  assert.throws(() => api.validateArtifacts(capture, gate), /CLAIM_GATE_EXPIRED/);
});

test("base64 conversion and sha256 are deterministic", async () => {
  const bytes = api.base64Bytes("AQIDBA==");
  assert.deepEqual([...bytes], [1, 2, 3, 4]);
  assert.equal(await api.sha256Hex(bytes), "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a");
});

test("browser signer source has no broadcast, RPC or secret operation", () => {
  const source = fs.readFileSync(path.join(__dirname, "../tools/claim_v2_sign_only/sign-only.js"), "utf8");
  for (const forbidden of ["sendTransaction", "sendRawTransaction", "privateKey", "secretKey", "seedPhrase"]) {
    assert.equal(source.includes(forbidden), false);
  }
  assert.equal((source.match(/fetch\(/g) || []).length, 2);
  assert.equal(source.includes('fetch("/jit/session"'), true);
  assert.equal(source.includes('fetch("/jit/prepare"'), true);
});
