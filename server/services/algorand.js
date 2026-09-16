import "dotenv/config";
const ALGOD_URL = process.env.ALGOD_URL || "https://testnet-api.algonode.cloud";
const INDEXER_URL = process.env.INDEXER_URL || "https://testnet-idx.algonode.cloud";
export async function getAlgodStatus() {
    const response = await fetch(`${ALGOD_URL}/v2/status`);
    if (!response.ok) {
        throw new Error(`Algod request failed: ${response.status}`);
    }
    return response.json();
}
export async function getAlgodHealth() {
    const response = await fetch(`${ALGOD_URL}/health`);
    return {
        ok: response.ok,
        status: response.status,
    };
}
export async function getAccountInfo(address) {
    const response = await fetch(`${ALGOD_URL}/v2/accounts/${encodeURIComponent(address)}`);
    if (!response.ok) {
        throw new Error(`Account lookup failed: ${response.status}`);
    }
    return response.json();
}
export async function getAssetInfo(assetId) {
    const response = await fetch(`${ALGOD_URL}/v2/assets/${assetId}`);
    if (!response.ok) {
        throw new Error(`Asset lookup failed: ${response.status}`);
    }
    return response.json();
}
export async function getIndexerHealth() {
    const response = await fetch(`${INDEXER_URL}/health`);
    return {
        ok: response.ok,
        status: response.status,
    };
}
// ============================================================
// TRANSACTION LOOKUP
// ============================================================
/**
 * A valid Algorand transaction ID is a 52-character base32 string
 * (RFC4648 alphabet, no padding: A-Z and 2-7).
 */
export function isValidAlgorandTxId(value) {
    return /^[A-Z2-7]{52}$/.test((value || "").trim().toUpperCase());
}
export function buildLoraTestnetTxUrl(txId) {
    return `https://lora.algokit.io/testnet/transaction/${txId}`;
}
export function buildLoraTestnetAddressUrl(address) {
    return `https://lora.algokit.io/testnet/account/${address}`;
}
/**
 * Fetch a confirmed (or pending) transaction from Algorand Testnet using
 * the Indexer first (richer historical data), falling back to Algod's
 * pending-transaction lookup if the Indexer hasn't caught up yet.
 *
 * Returns null if the transaction cannot be found anywhere.
 */
export async function getTransaction(rawTxId) {
    const txId = (rawTxId || "").trim().toUpperCase();
    if (!isValidAlgorandTxId(txId)) {
        throw new Error("INVALID_TRANSACTION_ID");
    }
    // Try the Indexer first.
    try {
        const response = await fetch(`${INDEXER_URL}/v2/transactions/${encodeURIComponent(txId)}`);
        if (response.ok) {
            const body = await response.json();
            return { source: "indexer", ...body };
        }
        if (response.status !== 404) {
            // Indexer reachable but returned a real error — surface it.
            throw new Error(`Indexer request failed: ${response.status}`);
        }
    }
    catch (error) {
        if (error?.message?.startsWith("Indexer request failed")) {
            throw error;
        }
        // network error — fall through to algod pending lookup
    }
    // Fall back to Algod's pending transaction endpoint (covers
    // very recently submitted transactions the Indexer hasn't indexed yet).
    try {
        const response = await fetch(`${ALGOD_URL}/v2/transactions/pending/${encodeURIComponent(txId)}`);
        if (response.ok) {
            const body = await response.json();
            return { source: "algod-pending", transaction: body };
        }
    }
    catch {
        // ignore, will return null below
    }
    return null;
}
/**
 * Normalize a raw indexer/algod transaction payload into the flat shape
 * the CargoProof Assistant needs, without leaking anything unnecessary.
 */
export function summarizeTransaction(raw, txId) {
    const source = raw?.source;
    const txn = source === "indexer" ? raw.transaction : raw?.transaction;
    if (!txn) {
        return {
            id: txId,
            confirmed: false,
            status: "PENDING_OR_UNKNOWN",
        };
    }
    const confirmedRound = txn["confirmed-round"] ?? null;
    const roundTime = txn["round-time"]
        ? new Date(txn["round-time"] * 1000).toISOString()
        : null;
    const assetTransfer = txn["asset-transfer-transaction"] || null;
    const payment = txn["payment-transaction"] || null;
    const appCall = txn["application-transaction"] || null;
    return {
        id: txn.id || txId,
        confirmed: Boolean(confirmedRound),
        status: confirmedRound ? "CONFIRMED" : "PENDING",
        confirmedRound,
        roundTime,
        sender: txn.sender || null,
        fee: typeof txn.fee === "number" ? txn.fee : null,
        txType: txn["tx-type"] || null,
        group: txn.group || null,
        note: txn.note || null,
        assetTransfer: assetTransfer
            ? {
                assetId: assetTransfer["asset-id"],
                amount: assetTransfer.amount,
                receiver: assetTransfer.receiver,
                closeTo: assetTransfer["close-to"] || null,
            }
            : null,
        payment: payment
            ? {
                amount: payment.amount,
                receiver: payment.receiver,
                closeAmount: payment["close-amount"] ?? null,
            }
            : null,
        applicationCall: appCall
            ? {
                applicationId: appCall["application-id"],
                appArgs: appCall["application-args"] || [],
                onCompletion: appCall["on-completion"] || null,
            }
            : null,
        innerTxns: txn["inner-txns"] || [],
        closeRekey: {
            closeRewards: txn["close-rewards"] ?? null,
            rekeyTo: txn["rekey-to"] || null,
        },
    };
}
