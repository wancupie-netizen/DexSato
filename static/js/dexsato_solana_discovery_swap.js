/* DexSato D6: the connected wallet, never DexSato, signs Jupiter swaps. */
(function () {
    "use strict";

    const sandbox = document.querySelector("[data-jupiter-sandbox]");
    if (!sandbox) return;

    const walletState = sandbox.querySelector("[data-wallet-state]");
    const connect = sandbox.querySelector("[data-connect-wallet]");
    const quoteButton = sandbox.querySelector("[data-get-quote]");
    const amount = sandbox.querySelector("[data-quote-amount]");
    const receiveAmount = sandbox.querySelector("[data-receive-amount]");
    const inputError = sandbox.querySelector("[data-swap-input-error]");
    const quoteResult = sandbox.querySelector("[data-quote-result]");
    const quoteCompact = sandbox.querySelector("[data-quote-compact]");
    const quoteDetails = sandbox.querySelector("[data-quote-details]");
    const compactMinimum = sandbox.querySelector("[data-compact-minimum]");
    const compactImpact = sandbox.querySelector("[data-compact-impact]");
    const compactFee = sandbox.querySelector("[data-compact-fee]");
    const acknowledgement = sandbox.querySelector("[data-swap-risk-ack]");
    const confirmationSummary = sandbox.querySelector("[data-confirmation-summary]");
    const swapButton = sandbox.querySelector("[data-execute-swap]");
    const swapResult = sandbox.querySelector("[data-swap-result]");
    const sideButtons = Array.from(document.querySelectorAll("[data-trade-side]"));
    const payCoin = sandbox.querySelector("[data-pay-coin]");
    const receiveCoin = sandbox.querySelector("[data-receive-coin]");
    const balanceLabel = sandbox.querySelector("[data-balance-label]");
    const routeSummary = sandbox.querySelector("[data-route-summary]");
    const amountNote = sandbox.querySelector("[data-amount-note]");
    const amountPresets = Array.from(document.querySelectorAll("[data-amount-preset]"));
    const tokenAddress = sandbox.dataset.tokenAddress;
    const tokenSymbol = sandbox.dataset.tokenSymbol || "token";
    const wrappedSolMint = "So11111111111111111111111111111111111111112";
    const sellRouteStatus = document.querySelector("[data-sell-route-status]");
    const apiBase = "/api/discovery/solana/" + encodeURIComponent(tokenAddress);
    let walletProvider = null;
    let walletAddress = "";
    let currentQuote = null;
    let pendingSignedOrder = null;
    let pendingUnsignedOrder = null;
    let quoteRevision = 0;
    let busy = false;
    let web3Promise = null;
    let side = "buy";

    document.querySelectorAll("[data-copy-address]").forEach(function (button) {
        button.addEventListener("click", async function () {
            try {
                await navigator.clipboard.writeText(button.dataset.copyAddress);
                button.textContent = "Copied";
                window.setTimeout(function () { button.textContent = "Copy"; }, 1600);
            } catch (_) {
                button.textContent = "Unavailable";
            }
        });
    });

    function present(value, fallback) {
        return value === null || value === undefined || value === ""
            ? fallback : String(value);
    }

    function currentWalletAddress() {
        return walletProvider && walletProvider.publicKey
            ? String(walletProvider.publicKey) : "";
    }

    function sameAmount(first, second) {
        const left = Number(first);
        const right = Number(second);
        return Number.isFinite(left) && Number.isFinite(right) && left === right;
    }

    function actionLabel() {
        return (side === "sell" ? "Sell " : "Buy ") + tokenSymbol;
    }

    function updateSwapAvailability() {
        swapButton.disabled = busy || !walletAddress || !currentQuote
            || currentQuote.side !== side
            || !sameAmount(currentQuote.input_amount_ui, amount.value)
            || currentWalletAddress() !== walletAddress
            || currentQuote.fee_disclosure.execution_ready !== true;
        amount.disabled = busy;
        quoteButton.disabled = busy;
        acknowledgement.disabled = busy;
        sideButtons.forEach(function (button) { button.disabled = busy; });
    }

    function clearPreparedState() {
        pendingSignedOrder = null;
        pendingUnsignedOrder = null;
    }

    function clearConfirmation() {
        pendingUnsignedOrder = null;
        confirmationSummary.hidden = true;
        confirmationSummary.replaceChildren();
        swapButton.textContent = actionLabel();
    }

    function setInputError(message) {
        const text = present(message, "");
        inputError.textContent = text;
        inputError.hidden = !text;
    }

    function clearQuote() {
        quoteRevision += 1;
        currentQuote = null;
        clearPreparedState();
        clearConfirmation();
        receiveAmount.textContent = "—";
        quoteCompact.hidden = true;
        quoteDetails.hidden = true;
        quoteDetails.open = false;
        sandbox.dataset.quoteReady = "false";
        quoteButton.textContent = "Get " + side + " quote";
        quoteResult.className = "quote-result quote-result-v27";
        quoteResult.replaceChildren();
        setInputError("");
        acknowledgement.checked = false;
        updateSwapAvailability();
    }

    function setResult(container, message, tone) {
        container.className = "quote-result visible" + (tone ? " " + tone : "");
        container.replaceChildren();
        const text = document.createElement(tone === "quote-error" ? "strong" : "p");
        text.textContent = message;
        container.appendChild(text);
    }

    function addSummaryRow(container, label, value, className) {
        const cell = document.createElement("div");
        cell.className = className || "quote-summary-row-v27";
        const caption = document.createElement("span");
        caption.textContent = label;
        const result = document.createElement("b");
        result.textContent = present(value, "Unavailable");
        cell.append(caption, result);
        container.appendChild(cell);
    }

    function outputSymbol(payload) {
        return payload.output_mint === wrappedSolMint ? "SOL" : tokenSymbol;
    }

    function inputSymbol(payload) {
        return payload.input_mint === wrappedSolMint ? "SOL" : tokenSymbol;
    }

    function tokenOutput(payload) {
        const symbol = outputSymbol(payload);
        if (payload.output_amount_ui) {
            const ui = Number(payload.output_amount_ui);
            return (Number.isFinite(ui)
                ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 8}).format(ui)
                : payload.output_amount_ui) + " " + symbol;
        }
        const raw = present(payload.output_amount_raw, "Unavailable");
        return raw.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " raw " + symbol + " units";
    }

    function compactOutput(payload) {
        if (payload.output_amount_ui) return tokenOutput(payload).replace(" " + outputSymbol(payload), "");
        const raw = Number(payload.output_amount_raw);
        return Number.isFinite(raw)
            ? new Intl.NumberFormat(undefined, {notation: "compact", maximumFractionDigits: 2}).format(raw)
                + " raw"
            : "—";
    }

    function minimumOutput(payload) {
        const symbol = outputSymbol(payload);
        if (payload.minimum_received_ui) {
            const ui = Number(payload.minimum_received_ui);
            return (Number.isFinite(ui)
                ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 8}).format(ui)
                : payload.minimum_received_ui) + " " + symbol;
        }
        const minimum = Number(payload.minimum_received_raw);
        const raw = Number(payload.output_amount_raw);
        const ui = Number(payload.output_amount_ui);
        if (payload.output_amount_ui && minimum > 0 && Number.isFinite(minimum)
                && Number.isFinite(raw) && raw > 0 && Number.isFinite(ui)) {
            return new Intl.NumberFormat(undefined, {maximumFractionDigits: 8})
                .format(minimum * (ui / raw)) + " " + symbol;
        }
        if (minimum > 0 && Number.isFinite(minimum)) {
            return String(payload.minimum_received_raw).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
                + " raw " + symbol + " units";
        }
        return "Unavailable";
    }

    function slippageText(payload) {
        const bps = Number(payload.slippage_bps);
        return Number.isFinite(bps) && bps > 0 ? (bps / 100).toFixed(2) + "%" : "Unavailable";
    }

    function impactText(payload) {
        const impact = Number(payload.price_impact_pct);
        return Number.isFinite(impact)
            ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 4}).format(impact) + "%"
            : "Unavailable";
    }

    function validFeeDisclosure(payload) {
        const fee = payload.fee_disclosure;
        if (!fee || fee.version !== 1 || typeof fee.policy_id !== "string"
            || !/^[a-f0-9]{64}$/.test(fee.policy_id)
            || fee.policy_id !== payload.dexsato_fee_policy_id
            || !Number.isInteger(fee.integrator_fee_bps)
            || fee.integrator_fee_bps !== payload.dexsato_integrator_fee_bps
            || typeof fee.integrator_fee_amount_ui !== "string"
            || !/^\d+(\.\d+)?$/.test(fee.integrator_fee_amount_ui)
            || fee.integrator_fee_percent !== (fee.integrator_fee_bps / 100).toFixed(2)) return false;
        if (fee.integrator_fee_bps === 0) {
            return fee.amount_kind === "ZERO" && Number(fee.integrator_fee_amount_ui) === 0
                && fee.execution_ready === true && !payload.dexsato_referral_account;
        }
        const previewOnly = fee.execution_ready === false
            && !["ONE_SHOT_TAP", "LIVE_REFERRAL"].includes(fee.activation_scope);
        const controlledOneShot = fee.execution_ready === true
            && fee.activation_scope === "ONE_SHOT_TAP"
            && fee.integrator_fee_bps === 50
            && payload.side === "buy"
            && payload.output_mint === "ADcF26nFGKMuRZ7va5361H2PCHCDRi2FmeJBkX3Spump"
            && payload.input_amount_lamports === "1000000";
        const liveReferral = fee.execution_ready === true
            && fee.activation_scope === "LIVE_REFERRAL";
        return fee.integrator_fee_bps >= 50 && fee.integrator_fee_bps <= 255
            && fee.amount_kind === "ESTIMATE" && fee.integrator_fee_symbol === "WSOL"
            && fee.referral_verification === "RPC_ACCOUNT_VERIFIED"
            && typeof payload.dexsato_referral_account === "string"
            && payload.dexsato_referral_account.length >= 32
            && (previewOnly || controlledOneShot || liveReferral);
    }

    function sameFeePolicy(first, second) {
        return validFeeDisclosure(first) && validFeeDisclosure(second)
            && first.dexsato_fee_policy_id === second.dexsato_fee_policy_id
            && first.dexsato_referral_account === second.dexsato_referral_account
            && first.dexsato_fee_mint === second.dexsato_fee_mint;
    }

    function renderFeeDisclosure(container, payload, className) {
        const fee = payload.fee_disclosure;
        const label = fee.integrator_fee_bps === 0 ? "DexSato fee" : "Estimated integrator fee";
        addSummaryRow(container, label, fee.integrator_fee_percent + "% · "
            + fee.integrator_fee_amount_ui + " " + fee.integrator_fee_symbol, className);
        if (fee.integrator_fee_bps > 0) {
            addSummaryRow(container, "Jupiter share (included)", fee.jupiter_share_percent + "% of fee", className);
            const activationLabel = fee.execution_ready === true
                && fee.activation_scope === "LIVE_REFERRAL"
                ? "Active · DexSato referral fee"
                : fee.execution_ready === true && fee.activation_scope === "ONE_SHOT_TAP"
                    ? "Armed · one controlled TAP swap"
                    : "Pending · quote preview only";
            addSummaryRow(container, "Fee activation", activationLabel, className);
        }
        const note = document.createElement("p");
        note.textContent = fee.note + " " + fee.network_fee_note;
        container.appendChild(note);
    }

    function renderQuote(payload) {
        quoteResult.className = "quote-result quote-result-v27 visible";
        quoteResult.replaceChildren();
        const header = document.createElement("div");
        header.className = "quote-preview-head-v27";
        const title = document.createElement("strong");
        title.textContent = (payload.side === "sell" ? "Sell" : "Buy") + " quote preview";
        const fresh = document.createElement("span");
        fresh.className = "quote-fresh-v27";
        fresh.textContent = "● Updated just now";
        header.append(title, fresh);
        const summary = document.createElement("div");
        summary.className = "quote-summary-v27";
        addSummaryRow(summary, "Expected receive", tokenOutput(payload));
        addSummaryRow(summary, "Minimum receive", minimumOutput(payload));
        addSummaryRow(summary, "Output decimals", payload.output_decimals == null
            ? "Unavailable · raw fallback"
            : String(payload.output_decimals) + " · "
                + present(payload.output_decimals_source, "verified mint"));
        addSummaryRow(summary, "Price impact", impactText(payload));
        addSummaryRow(summary, "Slippage", slippageText(payload));
        renderFeeDisclosure(summary, payload);
        addSummaryRow(summary, "Estimated network fee", "Shown by wallet");
        addSummaryRow(summary, "Route", present(payload.router, "Jupiter"));
        quoteResult.append(header, summary);
        compactMinimum.textContent = minimumOutput(payload);
        compactImpact.textContent = impactText(payload);
        compactFee.textContent = payload.fee_disclosure.integrator_fee_percent + "% · "
            + payload.fee_disclosure.integrator_fee_amount_ui + " "
            + payload.fee_disclosure.integrator_fee_symbol;
        quoteCompact.hidden = false;
        quoteDetails.hidden = false;
        sandbox.dataset.quoteReady = "true";
        swapButton.textContent = actionLabel();
        receiveAmount.textContent = compactOutput(payload);
        if (routeSummary) {
            routeSummary.textContent = inputSymbol(payload) + " → "
                + present(payload.router, "Jupiter") + " → " + outputSymbol(payload);
        }
        amountPresets.forEach(function (button) {
            button.textContent = side === "buy" ? button.dataset.buyValue : button.dataset.sellValue;
        });
    }

    async function requestJson(url, options) {
        const response = await fetch(url, Object.assign({credentials: "same-origin"}, options));
        let payload;
        try {
            payload = await response.json();
        } catch (_) {
            throw new Error("DexSato received an invalid provider response.");
        }
        if (!response.ok) {
            const error = new Error(present(payload.detail, "Swap request was rejected."));
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function transactionBytes(base64) {
        const binary = window.atob(base64);
        return Uint8Array.from(binary, function (character) { return character.charCodeAt(0); });
    }

    function base64Transaction(bytes) {
        let binary = "";
        bytes.forEach(function (byte) { binary += String.fromCharCode(byte); });
        return window.btoa(binary);
    }

    function loadSolanaWeb3() {
        if (window.solanaWeb3 && window.solanaWeb3.VersionedTransaction) {
            return Promise.resolve(window.solanaWeb3);
        }
        if (!web3Promise) {
            web3Promise = new Promise(function (resolve, reject) {
                const script = document.createElement("script");
                script.src = "https://cdn.jsdelivr.net/npm/@solana/web3.js@1.98.4/lib/index.iife.min.js";
                script.async = true;
                script.crossOrigin = "anonymous";
                script.onload = function () {
                    if (window.solanaWeb3 && window.solanaWeb3.VersionedTransaction) {
                        resolve(window.solanaWeb3);
                    } else {
                        reject(new Error("Solana transaction support did not initialize."));
                    }
                };
                script.onerror = function () {
                    reject(new Error("Solana transaction support could not be loaded."));
                };
                document.head.appendChild(script);
            }).catch(function (error) {
                web3Promise = null;
                throw error;
            });
        }
        return web3Promise;
    }

    function applySide(next, resetAmount) {
        if (busy || (next !== "buy" && next !== "sell")) return;
        side = next;
        sandbox.dataset.side = side;
        sideButtons.forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset.tradeSide === side));
        });
        if (payCoin) payCoin.textContent = side === "buy" ? "◎ SOL" : tokenSymbol;
        if (receiveCoin) receiveCoin.textContent = side === "buy" ? tokenSymbol : "◎ SOL";
        if (balanceLabel) {
            balanceLabel.textContent = side === "buy"
                ? "SOL balance checked at order"
                : tokenSymbol + " balance checked at order";
        }
        if (amountNote) {
            amountNote.textContent = side === "buy"
                ? "Enter an amount between 0.001 and 100 SOL"
                : "Enter the exact token amount to sell";
        }
        if (routeSummary) {
            routeSummary.textContent = side === "buy"
                ? "SOL → Jupiter → " + tokenSymbol
                : tokenSymbol + " → Jupiter → SOL";
        }
        if (resetAmount !== false) amount.value = side === "buy" ? "0.1" : "1";
        quoteButton.textContent = "Get " + side + " quote";
        clearQuote();
    }

    sideButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            applySide(button.dataset.tradeSide, true);
        });
    });

    amountPresets.forEach(function (button) {
        button.addEventListener("click", function () {
            amount.value = side === "buy" ? button.dataset.buyValue : button.dataset.sellValue;
            clearQuote();
            amount.focus();
        });
    });

    async function relaySignedOrder(pending) {
        if (Date.parse(pending.expires_at) <= Date.now()) {
            clearPreparedState();
            throw new Error("The signed swap order expired. Request a new quote and try again.");
        }
        if (currentWalletAddress() !== pending.wallet_address) {
            clearPreparedState();
            throw new Error("The connected wallet changed before the signed swap was submitted.");
        }
        setResult(swapResult, "Submitting the wallet-approved transaction through Jupiter…");
        const result = await requestJson(apiBase + "/jupiter-execute", {
            method: "POST",
            headers: {"content-type": "application/json", accept: "application/json"},
            body: JSON.stringify({
                request_id: pending.request_id,
                wallet_address: pending.wallet_address,
                signed_transaction: pending.signed_transaction
            })
        });
        clearPreparedState();
        if (result.status !== "SWAP_CONFIRMED") {
            throw new Error(present(result.error, "Jupiter could not settle the swap."));
        }
        if (result.side !== pending.side || result.input_mint !== pending.input_mint
                || result.output_mint !== pending.output_mint) {
            throw new Error("The settlement result did not match the wallet-approved trade.");
        }
        swapResult.className = "quote-result visible swap-success";
        swapResult.replaceChildren();
        const heading = document.createElement("strong");
        heading.textContent = "Swap confirmed on Solana";
        const signature = document.createElement("p");
        signature.textContent = "Transaction: " + result.signature;
        const explorer = document.createElement("a");
        explorer.href = "https://solscan.io/tx/" + encodeURIComponent(result.signature);
        explorer.target = "_blank";
        explorer.rel = "noopener noreferrer";
        explorer.textContent = "Verify transaction on Solscan ↗";
        swapResult.append(heading, signature, explorer);
        clearQuote();
    }

    connect.addEventListener("click", async function () {
        const provider = window.phantom && window.phantom.solana
            ? window.phantom.solana : window.solana;
        if (!provider || typeof provider.connect !== "function") {
            walletState.textContent = "Supported Solana wallet not detected.";
            return;
        }
        connect.disabled = true;
        try {
            const connection = await provider.connect();
            const key = connection && connection.publicKey ? connection.publicKey : provider.publicKey;
            if (!key || typeof provider.signTransaction !== "function") {
                throw new Error("This wallet does not support transaction approval.");
            }
            walletProvider = provider;
            walletAddress = String(key);
            walletState.textContent = walletAddress.slice(0, 4) + "…"
                + walletAddress.slice(-4) + " · Connected";
            walletState.classList.add("connected");
            connect.textContent = "Change";
            clearPreparedState();
            if (typeof provider.on === "function") {
                provider.on("accountChanged", function (publicKey) {
                    const changed = publicKey ? String(publicKey) : "";
                    if (changed !== walletAddress) {
                        walletAddress = changed;
                        walletState.textContent = changed
                            ? changed.slice(0, 4) + "…" + changed.slice(-4) + " · Connected"
                            : "Wallet disconnected.";
                        walletState.classList.toggle("connected", Boolean(changed));
                        clearQuote();
                    }
                });
                provider.on("disconnect", function () {
                    walletAddress = "";
                    walletState.textContent = "Wallet disconnected.";
                    walletState.classList.remove("connected");
                    clearQuote();
                });
            }
        } catch (error) {
            walletState.classList.remove("connected");
            walletState.textContent = present(error.message, "Wallet connection was not approved.");
        } finally {
            connect.disabled = false;
            updateSwapAvailability();
        }
    });

    quoteButton.addEventListener("click", async function () {
        if (busy) return;
        clearQuote();
        const revision = quoteRevision;
        quoteButton.disabled = true;
        quoteButton.textContent = "Fetching quote…";
        swapResult.className = "quote-result";
        swapResult.replaceChildren();
        setResult(swapResult, "Getting the latest Jupiter quote…");
        try {
            const payload = await requestJson(
                apiBase + "/jupiter-quote?side=" + encodeURIComponent(side)
                    + "&amount=" + encodeURIComponent(amount.value),
                {headers: {accept: "application/json"}}
            );
            if (revision !== quoteRevision) return;
            const expectedInputMint = side === "buy" ? wrappedSolMint : tokenAddress;
            const expectedOutputMint = side === "buy" ? tokenAddress : wrappedSolMint;
            if (payload.side !== side || payload.token_mint !== tokenAddress
                || payload.input_mint !== expectedInputMint || payload.output_mint !== expectedOutputMint
                || !sameAmount(payload.input_amount_ui, amount.value)
                || !validFeeDisclosure(payload)) {
                throw new Error("The returned quote did not match the approved DexSato policy.");
            }
            currentQuote = payload;
            renderQuote(payload);
            swapResult.className = "quote-result";
            swapResult.replaceChildren();
            if (sellRouteStatus && side === "sell") {
                sellRouteStatus.textContent = "Verified · just now";
                sellRouteStatus.classList.add("verified");
            }
        } catch (error) {
            if (revision !== quoteRevision) return;
            setResult(swapResult, present(error.message, "Jupiter quote is unavailable."), "quote-error");
        } finally {
            quoteButton.disabled = false;
            quoteButton.textContent = currentQuote ? "Refresh quote" : "Get " + side + " quote";
            updateSwapAvailability();
        }
    });

    amount.addEventListener("input", clearQuote);
    acknowledgement.addEventListener("change", function () {
        if (!acknowledgement.checked) clearConfirmation();
        updateSwapAvailability();
    });

    swapButton.addEventListener("click", async function () {
        if (busy || !walletAddress || !currentQuote) return;
        acknowledgement.checked = true;
        busy = true;
        swapButton.textContent = "Preparing secure order…";
        updateSwapAvailability();
        try {
            if (pendingSignedOrder) {
                await relaySignedOrder(pendingSignedOrder);
                return;
            }
            setResult(swapResult, "Preparing secure Solana transaction support…");
            const solanaWeb3 = await loadSolanaWeb3();
            if (!currentQuote || !acknowledgement.checked) {
                throw new Error("The trade changed. Request a new quote and review it again.");
            }
            if (currentWalletAddress() !== walletAddress) {
                throw new Error("The connected wallet changed. Connect it again before swapping.");
            }
            setResult(swapResult, "Preparing an unsigned Jupiter mainnet transaction…");
            const revision = quoteRevision;
            let order = pendingUnsignedOrder;
            if (!order) {
                order = await requestJson(apiBase + "/jupiter-order", {
                    method: "POST",
                    headers: {"content-type": "application/json", accept: "application/json"},
                    body: JSON.stringify({
                        amount: amount.value,
                        side: side,
                        wallet_address: walletAddress,
                        risk_acknowledged: acknowledgement.checked
                    })
                });
                if (revision !== quoteRevision || !currentQuote || !acknowledgement.checked) {
                    throw new Error("The trade changed. Request a new quote and review it again.");
                }
            }
            const expectedInputMint = side === "buy" ? wrappedSolMint : tokenAddress;
            const expectedOutputMint = side === "buy" ? tokenAddress : wrappedSolMint;
            if (order.wallet_address !== walletAddress || order.side !== side
                || order.token_mint !== tokenAddress
                || order.input_mint !== expectedInputMint || order.output_mint !== expectedOutputMint
                || !sameAmount(order.input_amount_ui, amount.value)
                || !sameFeePolicy(currentQuote, order) || order.fee_disclosure.execution_ready !== true) {
                throw new Error("The prepared order did not match the reviewed token, wallet, or amount.");
            }
            if (!Number.isFinite(Date.parse(order.expires_at)) || Date.parse(order.expires_at) <= Date.now()) {
                pendingUnsignedOrder = null;
                throw new Error("The Jupiter order expired before wallet approval.");
            }
            if (!pendingUnsignedOrder) {
                pendingUnsignedOrder = order;
            }
            if (currentWalletAddress() !== walletAddress) {
                throw new Error("The connected wallet changed before signing. Reconnect and review again.");
            }
            const unsigned = solanaWeb3.VersionedTransaction.deserialize(
                transactionBytes(order.unsigned_transaction)
            );
            swapButton.textContent = "Waiting for wallet…";
            setResult(swapResult, "Review and approve this swap in your connected wallet.");
            const signed = await walletProvider.signTransaction(unsigned);
            if (currentWalletAddress() !== walletAddress) {
                throw new Error("The connected wallet changed during transaction approval.");
            }
            if (!signed || typeof signed.serialize !== "function") {
                throw new Error("The connected wallet did not return a signed transaction.");
            }
            pendingSignedOrder = {
                request_id: order.request_id,
                wallet_address: walletAddress,
                expires_at: order.expires_at,
                side: order.side,
                input_mint: order.input_mint,
                output_mint: order.output_mint,
                signed_transaction: base64Transaction(signed.serialize())
            };
            await relaySignedOrder(pendingSignedOrder);
        } catch (error) {
            const message = present(error.message, "Jupiter swap could not be completed.");
            const insufficientBalance = /insufficient (sol|token) balance/i.test(message);
            if (error.status === 400 || error.status === 410) {
                clearPreparedState();
                clearConfirmation();
                acknowledgement.checked = false;
            }
            if (insufficientBalance) {
                setInputError(message);
                swapResult.className = "quote-result";
                swapResult.replaceChildren();
                amount.focus();
                amount.select();
            }
            if (pendingSignedOrder) swapButton.textContent = "Retry signed transaction";
            if (!insufficientBalance) setResult(swapResult, message, "quote-error");
        } finally {
            busy = false;
            if (!pendingSignedOrder) swapButton.textContent = actionLabel();
            updateSwapAvailability();
        }
    });

    applySide("buy", false);
})();
