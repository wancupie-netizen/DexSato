/* DexSato D6: the connected wallet, never DexSato, signs Jupiter swaps. */
(function () {
    "use strict";

    const sandbox = document.querySelector("[data-jupiter-sandbox]");
    if (!sandbox) return;

    const walletState = sandbox.querySelector("[data-wallet-state]");
    const connect = sandbox.querySelector("[data-connect-wallet]");
    const quoteButton = sandbox.querySelector("[data-get-quote]");
    const amount = sandbox.querySelector("[data-quote-amount]");
    const quoteResult = sandbox.querySelector("[data-quote-result]");
    const acknowledgement = sandbox.querySelector("[data-swap-risk-ack]");
    const swapButton = sandbox.querySelector("[data-execute-swap]");
    const swapResult = sandbox.querySelector("[data-swap-result]");
    const tokenAddress = sandbox.dataset.tokenAddress;
    const tokenSymbol = sandbox.dataset.tokenSymbol || "token";
    const apiBase = "/api/discovery/solana/" + encodeURIComponent(tokenAddress);
    let walletProvider = null;
    let walletAddress = "";
    let currentQuote = null;
    let pendingSignedOrder = null;
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
        swapButton.textContent = "Review and approve swap";
    }

    function clearQuote() {
        currentQuote = null;
        clearPreparedState();
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

    function addCell(grid, label, value) {
        const cell = document.createElement("div");
        cell.className = "quote-cell";
        const caption = document.createElement("span");
        caption.textContent = label;
        const result = document.createElement("b");
        result.textContent = present(value, "Unavailable");
        cell.append(caption, result);
        grid.appendChild(cell);
    }

    function addFee(container, label, value) {
        const row = document.createElement("div");
        row.className = "fee-row";
        const caption = document.createElement("span");
        caption.textContent = label;
        const amountText = document.createElement("b");
        amountText.textContent = present(value, 0) + " bps";
        row.append(caption, amountText);
        container.appendChild(row);
    }

    function renderQuote(payload) {
        quoteResult.className = "quote-result visible";
        quoteResult.replaceChildren();
        const grid = document.createElement("div");
        grid.className = "quote-grid";
        const output = payload.output_amount_ui
            ? payload.output_amount_ui + " " + tokenSymbol
            : payload.output_amount_raw + " raw token units";
        addCell(grid, "Expected output", output);
        addCell(grid, "Router", present(payload.router, "Jupiter"));
        addCell(grid, "Price impact", payload.price_impact_pct === null
            || payload.price_impact_pct === undefined
            ? "Unavailable" : payload.price_impact_pct + "%");
        addCell(grid, "Quote mode", present(payload.mode, "ExactIn"));
        quoteResult.appendChild(grid);
        addFee(quoteResult, "Jupiter / route fee", payload.jupiter_fee_bps);
        addFee(quoteResult, "DexSato integrator fee", payload.dexsato_integrator_fee_bps);
        const policy = document.createElement("p");
        policy.className = "quote-policy";
        policy.textContent = "Indicative quote · " + present(payload.as_of, "Time unavailable")
            + ". Final output is confirmed only after settlement.";
        quoteResult.appendChild(policy);
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
            walletState.textContent = "Connected public key · " + walletAddress;
            connect.textContent = "Wallet connected";
            clearPreparedState();
            if (typeof provider.on === "function") {
                provider.on("accountChanged", function (publicKey) {
                    const changed = publicKey ? String(publicKey) : "";
                    if (changed !== walletAddress) {
                        walletAddress = changed;
                        walletState.textContent = changed
                            ? "Wallet changed · " + changed : "Wallet disconnected.";
                        clearQuote();
                    }
                });
                provider.on("disconnect", function () {
                    walletAddress = "";
                    walletState.textContent = "Wallet disconnected.";
                    clearQuote();
                });
            }
        } catch (error) {
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
        } catch (error) {
            setResult(quoteResult, present(error.message, "Jupiter quote is unavailable."), "quote-error");
        } finally {
            quoteButton.disabled = false;
            quoteButton.textContent = "Get Jupiter quote";
            updateSwapAvailability();
        }
    });

    amount.addEventListener("input", clearQuote);
    acknowledgement.addEventListener("change", updateSwapAvailability);

    swapButton.addEventListener("click", async function () {
        if (busy || !walletAddress || !currentQuote || !acknowledgement.checked) return;
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
            if (error.status === 400 || error.status === 410) clearPreparedState();
            if (pendingSignedOrder) swapButton.textContent = "Retry signed transaction";
            setResult(swapResult, present(error.message, "Jupiter swap could not be completed."), "quote-error");
        } finally {
            busy = false;
            updateSwapAvailability();
        }
    });

    updateSwapAvailability();
})();
