"use strict";

(function (root) {
  const HASH = /^[0-9a-f]{64}$/;

  function requireCondition(condition, code) {
    if (!condition) throw new Error(code);
  }

  function base64Bytes(value) {
    requireCondition(typeof value === "string" && value.length > 0 && value.length <= 22000, "INVALID_UNSIGNED_TRANSACTION");
    const binary = atob(value);
    const result = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) result[index] = binary.charCodeAt(index);
    return result;
  }

  async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
  }

  function validateArtifacts(capture, gate, now = Date.now()) {
    requireCondition(capture && capture.status === "SDK_UNSIGNED_CAPTURED", "FRESH_UNSIGNED_CAPTURE_REQUIRED");
    requireCondition(capture.execution_ready === false && capture.fee_receipt_verified === false, "UNSAFE_CAPTURE_FLAGS");
    requireCondition(HASH.test(capture.message_sha256) && HASH.test(capture.transaction_sha256), "INVALID_CAPTURE_HASHES");
    requireCondition(capture.identity && capture.identity.payer === capture.identity.partner, "PAYER_PARTNER_MISMATCH");
    requireCondition(gate && gate.status === "ARMED", "ARMED_GATE_REQUIRED");
    requireCondition(gate.message_sha256 === capture.message_sha256 && gate.unsigned_transaction_sha256 === capture.transaction_sha256, "GATE_CAPTURE_HASH_MISMATCH");
    requireCondition(gate.partner === capture.identity.partner && gate.referral_account === capture.identity.referral_account && gate.mint === capture.identity.mint, "GATE_CAPTURE_IDENTITY_MISMATCH");
    requireCondition(gate.exact_claim_raw === "5000" && gate.expected_partner_raw === "4000" && gate.expected_project_raw === "1000", "CLAIM_AMOUNT_MISMATCH");
    requireCondition(gate.approval_count === 0 && gate.submission_attempt_count === 0 && gate.wallet_review_count === 0, "GATE_ALREADY_USED");
    requireCondition(gate.live_claim_approved === false && gate.claim_submitted === false && gate.execution_ready === false, "UNSAFE_GATE_FLAGS");
    const expiry = Date.parse(gate.expires_at);
    requireCondition(Number.isFinite(expiry) && expiry > now, "CLAIM_GATE_EXPIRED");
    return { wallet: capture.identity.partner, gateId: gate.gate_id };
  }

  async function readJsonFile(file) {
    requireCondition(file && file.size > 0 && file.size <= 131072, "INVALID_JSON_FILE_SIZE");
    const value = JSON.parse(await file.text());
    requireCondition(value && typeof value === "object" && !Array.isArray(value), "INVALID_JSON_OBJECT");
    return value;
  }

  function downloadBinary(bytes, gateId) {
    const blob = new Blob([bytes], { type: "application/octet-stream" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `claim_v2_signed_${gateId}.bin`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function signSelected(captureFile, gateFile) {
    const capture = await readJsonFile(captureFile);
    const gate = await readJsonFile(gateFile);
    const identity = validateArtifacts(capture, gate);
    const provider = root.solana;
    requireCondition(provider && typeof provider.connect === "function" && typeof provider.signTransaction === "function", "COMPATIBLE_SOLANA_WALLET_REQUIRED");
    requireCondition(root.solanaWeb3 && root.solanaWeb3.VersionedTransaction, "PINNED_WEB3_BUNDLE_REQUIRED");
    const unsignedBytes = base64Bytes(capture.transaction);
    requireCondition(await sha256Hex(unsignedBytes) === capture.transaction_sha256, "UNSIGNED_TRANSACTION_HASH_MISMATCH");
    const transaction = root.solanaWeb3.VersionedTransaction.deserialize(unsignedBytes);
    const messageBytes = transaction.message.serialize();
    requireCondition(await sha256Hex(messageBytes) === capture.message_sha256, "UNSIGNED_MESSAGE_HASH_MISMATCH");
    const connection = await provider.connect({ onlyIfTrusted: false });
    requireCondition(connection.publicKey && connection.publicKey.toString() === identity.wallet, "WALLET_IDENTITY_MISMATCH");
    const signed = await provider.signTransaction(transaction);
    const signedMessage = signed.message.serialize();
    requireCondition(await sha256Hex(signedMessage) === capture.message_sha256, "WALLET_CHANGED_MESSAGE");
    const signedBytes = signed.serialize();
    const signedHash = await sha256Hex(signedBytes);
    downloadBinary(signedBytes, identity.gateId);
    return { status: "WALLET_SIGNED_BINARY_DOWNLOADED_NO_SUBMISSION", gate_id: identity.gateId, message_sha256: capture.message_sha256, signed_transaction_sha256: signedHash, signed_transaction_persisted_by_server: false, live_claim_approved: false, submission_attempt_count: 0, transaction_submitted: false, execution_ready: false };
  }

  async function signJit() {
    const provider = root.solana;
    requireCondition(provider && typeof provider.connect === "function" &&
      typeof provider.signTransaction === "function", "COMPATIBLE_SOLANA_WALLET_REQUIRED");
    const connection = await provider.connect({ onlyIfTrusted: false });
    const sessionResponse = await fetch("/jit/session", { cache: "no-store" });
    requireCondition(sessionResponse.ok, "JIT_SESSION_UNAVAILABLE");
    const session = await sessionResponse.json();
    requireCondition(session.status === "JIT_SESSION_READY" && !session.used,
      "JIT_SESSION_ALREADY_USED");
    const response = await fetch("/jit/prepare", { method: "POST",
      headers: { "X-DexSato-JIT-Token": session.token }, body: null });
    const payload = await response.json();
    requireCondition(response.ok && payload.status === "JIT_UNSIGNED_ARTIFACTS_READY",
      payload.reason || "JIT_PREPARATION_FAILED");
    const identity = validateArtifacts(payload.capture, payload.gate);
    requireCondition(payload.handoff && payload.handoff.status ===
      "CLAIM_V2_JIT_SIGNING_HANDOFF_READY", "JIT_HANDOFF_REQUIRED");
    requireCondition(connection.publicKey && connection.publicKey.toString() === identity.wallet,
      "WALLET_IDENTITY_MISMATCH");
    const unsignedBytes = base64Bytes(payload.capture.transaction);
    requireCondition(await sha256Hex(unsignedBytes) === payload.capture.transaction_sha256,
      "UNSIGNED_TRANSACTION_HASH_MISMATCH");
    const transaction = root.solanaWeb3.VersionedTransaction.deserialize(unsignedBytes);
    requireCondition(await sha256Hex(transaction.message.serialize()) ===
      payload.capture.message_sha256, "UNSIGNED_MESSAGE_HASH_MISMATCH");
    const signed = await provider.signTransaction(transaction);
    requireCondition(await sha256Hex(signed.message.serialize()) ===
      payload.capture.message_sha256, "WALLET_CHANGED_MESSAGE");
    const signedBytes = signed.serialize();const signedHash = await sha256Hex(signedBytes);
    downloadBinary(signedBytes, identity.gateId);
    return { status:"WALLET_SIGNED_BINARY_DOWNLOADED_NO_SUBMISSION",
      gate_id:identity.gateId,message_sha256:payload.capture.message_sha256,
      signed_transaction_sha256:signedHash,signed_transaction_persisted_by_server:false,
      live_claim_approved:false,submission_attempt_count:0,
      transaction_submitted:false,execution_ready:false };
  }

  const api = Object.freeze({ base64Bytes, sha256Hex, validateArtifacts, signSelected, signJit });
  root.DexSatoClaimSignOnly = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (root.document) {
    const capture = document.getElementById("capture");
    const gate = document.getElementById("gate");
    const confirm = document.getElementById("confirm");
    const button = document.getElementById("sign");
    const status = document.getElementById("status");
    const jit = document.getElementById("jit");
    let used = false;
    function update() { button.disabled = used || !capture.files[0] || !gate.files[0] || !confirm.checked; }
    capture.addEventListener("change", update); gate.addEventListener("change", update); confirm.addEventListener("change", update);
    button.addEventListener("click", async () => {
      used = true; update(); status.textContent = "Validating exact artifacts before wallet prompt…";
      try {
        const report = await signSelected(capture.files[0], gate.files[0]);
        status.textContent = JSON.stringify(report, null, 2);
        status.className = "ok";
      } catch (error) {
        status.textContent = `STOP: ${error instanceof Error ? error.message : "SIGN_ONLY_FAILURE"}`;
      }
    });
    jit.addEventListener("click", async () => {
      jit.disabled=true;status.textContent="Generating fresh transaction after wallet readiness…";
      try { const report=await signJit();status.textContent=JSON.stringify(report,null,2);
        status.className="ok"; }
      catch(error){status.textContent=`STOP: ${error instanceof Error?error.message:"JIT_SIGN_ONLY_FAILURE"}`;}
    });
  }
})(typeof window !== "undefined" ? window : globalThis);
