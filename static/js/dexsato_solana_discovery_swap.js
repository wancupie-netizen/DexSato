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
    const acknowledgement = sandbox.querySelector("[data-swap-risk-ack]");
    const confirmationSummary = sandbox.querySelector("[data-confirmation-summary]");
    const swapButton = sandbox.querySelector("[data-execute-swap]");
    const swapResult = sandbox.querySelector("[data-swap-result]");
    const tokenAddress = sandbox.dataset.tokenAddress;
    const tokenSymbol = sandbox.dataset.tokenSymbol || "token";
    const sellRouteStatus = document.querySelector("[data-sell-route-status]");
    const apiBase = "/api/discovery/solana/" + encodeURIComponent(tokenAddress);
    let walletProvider = null;
    let walletAddress = "";
    let currentQuote = null;
    let pendingSignedOrder = null;
    let confirmationOpen = false;
    let busy = false;
    let web3Promise = null;

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

    function updateSwapAvailability() {
        swapButton.disabled = busy || !walletAddress || !currentQuote
            || !acknowledgement.checked
            || !sameAmount(currentQuote.input_amount_sol, amount.value)
            || currentWalletAddress() !== walletAddress;
    }

    function clearPreparedState() {
        pendingSignedOrder = null;
    }

    function clearConfirmation() {
        confirmationOpen = false;
        confirmationSummary.hidden = true;
        confirmationSummary.replaceChildren();
        swapButton.textContent = "Review transaction";
    }

    function setInputError(message) {
        const text = present(message, "");
        inputError.textContent = text;
        inputError.hidden = !text;
    }

    function clearQuote() {
        currentQuote = null;
        clearPreparedState();
        clearConfirmation();
        receiveAmount.textContent = "—";
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

    function tokenOutput(payload) {
        if (payload.output_amount_ui) {
            const ui = Number(payload.output_amount_ui);
            return (Number.isFinite(ui)
                ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 8}).format(ui)
                : payload.output_amount_ui) + " " + tokenSymbol;
        }
        const raw = present(payload.output_amount_raw, "Unavailable");
        return raw.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " raw token units";
    }

    function compactOutput(payload) {
        if (payload.output_amount_ui) return tokenOutput(payload).replace(" " + tokenSymbol, "");
        const raw = Number(payload.output_amount_raw);
        return Number.isFinite(raw)
            ? new Intl.NumberFormat(undefined, {notation: "compact", maximumFractionDigits: 2}).format(raw)
                + " raw"
            : "—";
    }

    function minimumOutput(payload) {
        if (payload.minimum_received_ui) {
            const ui = Number(payload.minimum_received_ui);
            return (Number.isFinite(ui)
                ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 8}).format(ui)
                : payload.minimum_received_ui) + " " + tokenSymbol;
        }
        const minimum = Number(payload.minimum_received_raw);
        const raw = Number(payload.output_amount_raw);
        const ui = Number(payload.output_amount_ui);
        if (payload.output_amount_ui && minimum > 0 && Number.isFinite(minimum)
                && Number.isFinite(raw) && raw > 0 && Number.isFinite(ui)) {
            return new Intl.NumberFormat(undefined, {maximumFractionDigits: 8})
                .format(minimum * (ui / raw)) + " " + tokenSymbol;
        }
        if (minimum > 0 && Number.isFinite(minimum)) {
            return String(payload.minimum_received_raw).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
                + " raw token units";
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

    function renderQuote(payload) {
        quoteResult.className = "quote-result quote-result-v27 visible";
        quoteResult.replaceChildren();
        const header = document.createElement("div");
        header.className = "quote-preview-head-v27";
        const title = document.createElement("strong");
        title.textContent = "Quote preview";
        const fresh = document.createElement("span");
        fresh.className = "quote-fresh-v27";
        fresh.textContent = "● Updated just now";
        header.append(title, fresh);
        const summary = document.createElement("div");
        summary.className = "quote-summary-v27";
        addSummaryRow(summary, "Expected receive", tokenOutput(payload));
        addSummaryRow(summary, "Minimum receive", minimumOutput(payload));
        addSummaryRow(summary, "Token decimals", payload.output_decimals == null
            ? "Unavailable · raw fallback"
            : String(payload.output_decimals) + " · "
                + present(payload.output_decimals_source, "verified mint"));
        addSummaryRow(summary, "Price impact", impactText(payload));
        addSummaryRow(summary, "Slippage", slippageText(payload));
        addSummaryRow(summary, "Estimated network fee", "Shown by wallet");
        addSummaryRow(summary, "Route", present(payload.router, "Jupiter"));
        quoteResult.append(header, summary);
        receiveAmount.textContent = compactOutput(payload);
    }

    function renderConfirmation(payload) {
        confirmationSummary.replaceChildren();
        const heading = document.createElement("h4");
        heading.textContent = "Confirmation summary";
        const note = document.createElement("p");
        note.textContent = "Check these details before opening your wallet.";
        const list = document.createElement("div");
        list.className = "confirmation-list-v27";
        addSummaryRow(list, "You pay", amount.value + " SOL", "confirmation-row-v27");
        addSummaryRow(list, "Expected receive", tokenOutput(payload), "confirmation-row-v27");
        addSummaryRow(list, "Minimum receive", minimumOutput(payload), "confirmation-row-v27");
        addSummaryRow(list, "Token decimals", payload.output_decimals == null
            ? "Unavailable · raw fallback"
            : String(payload.output_decimals) + " · "
                + present(payload.output_decimals_source, "verified mint"), "confirmation-row-v27");
        addSummaryRow(list, "Price impact", impactText(payload), "confirmation-row-v27");
        addSummaryRow(list, "Slippage", slippageText(payload), "confirmation-row-v27");
        addSummaryRow(list, "Network fee", "Confirmed by wallet", "confirmation-row-v27");
        confirmationSummary.append(heading, note, list);
        confirmationSummary.hidden = false;
        confirmationOpen = true;
        swapButton.textContent = "Confirm in wallet";
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
        clearQuote();
        quoteButton.disabled = true;
        quoteButton.textContent = "Fetching quote…";
        setResult(quoteResult, "Requesting an indicative Jupiter quote…");
        try {
            const payload = await requestJson(
                apiBase + "/jupiter-quote?amount_sol=" + encodeURIComponent(amount.value),
                {headers: {accept: "application/json"}}
            );
            if (payload.output_mint !== tokenAddress || payload.dexsato_integrator_fee_bps !== 0) {
                throw new Error("The returned quote did not match the approved DexSato policy.");
            }
            currentQuote = payload;
            renderQuote(payload);
            if (sellRouteStatus) {
                sellRouteStatus.textContent = "Verified · just now";
                sellRouteStatus.classList.add("verified");
            }
        } catch (error) {
            setResult(quoteResult, present(error.message, "Jupiter quote is unavailable."), "quote-error");
        } finally {
            quoteButton.disabled = false;
            quoteButton.textContent = "Get Jupiter quote";
            updateSwapAvailability();
        }
    });

    amount.addEventListener("input", clearQuote);
    acknowledgement.addEventListener("change", function () {
        if (!acknowledgement.checked) clearConfirmation();
        updateSwapAvailability();
    });

    swapButton.addEventListener("click", async function () {
        if (busy || !walletAddress || !currentQuote || !acknowledgement.checked) return;
        if (!confirmationOpen) {
            renderConfirmation(currentQuote);
            updateSwapAvailability();
            return;
        }
        busy = true;
        updateSwapAvailability();
        try {
            if (pendingSignedOrder) {
                await relaySignedOrder(pendingSignedOrder);
                return;
            }
            setResult(swapResult, "Preparing secure Solana transaction support…");
            const solanaWeb3 = await loadSolanaWeb3();
            if (currentWalletAddress() !== walletAddress) {
                throw new Error("The connected wallet changed. Connect it again before swapping.");
            }
            setResult(swapResult, "Preparing an unsigned Jupiter mainnet transaction…");
            const order = await requestJson(apiBase + "/jupiter-order", {
                method: "POST",
                headers: {"content-type": "application/json", accept: "application/json"},
                body: JSON.stringify({
                    amount_sol: amount.value,
                    wallet_address: walletAddress,
                    risk_acknowledged: acknowledgement.checked
                })
            });
            if (order.wallet_address !== walletAddress || order.output_mint !== tokenAddress
                || !sameAmount(order.input_amount_sol, amount.value)
                || order.dexsato_integrator_fee_bps !== 0) {
                throw new Error("The prepared order did not match the reviewed token, wallet, or amount.");
            }
            if (Date.parse(order.expires_at) <= Date.now()) {
                throw new Error("The Jupiter order expired before wallet approval.");
            }
            const unsigned = solanaWeb3.VersionedTransaction.deserialize(
                transactionBytes(order.unsigned_transaction)
            );
            setResult(swapResult, "Review the swap carefully and approve it in your connected wallet.");
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
                signed_transaction: base64Transaction(signed.serialize())
            };
            await relaySignedOrder(pendingSignedOrder);
        } catch (error) {
            const message = present(error.message, "Jupiter swap could not be completed.");
            const insufficientBalance = /insufficient sol balance/i.test(message);
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
            updateSwapAvailability();
        }
    });

    updateSwapAvailability();
})();
