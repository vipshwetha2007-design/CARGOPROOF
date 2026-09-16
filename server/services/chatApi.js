import { Hono } from "hono";
import { getTransaction, summarizeTransaction, isValidAlgorandTxId, buildLoraTestnetTxUrl, } from "./algorand.js";
import { explainWithLLM } from "./llmProvider.js";
/**
 * CargoProof Assistant
 * --------------------
 * Architecture:
 *
 *   User message
 *       -> deterministic intent detection (regex) + shipment/tx extraction
 *       -> existing CargoProof backend endpoints (source of truth):
 *            /api/v1/shipments/:id   (evidence store)
 *            /api/v1/vessels/:imo
 *            /api/v1/containers/:number
 *            /api/reset               (real verification engine + x402 flow)
 *            /api/state                (live escrow / evidence / payments)
 *            Algorand Indexer/Algod    (real transaction lookup)
 *       -> structured result
 *       -> LLM (Gemini/Groq) turns the structured result into plain language
 *       -> User
 *
 * The LLM never invents shipment, payment, or transaction facts — it only
 * receives already-verified structured data and is instructed to restate
 * it faithfully. If no LLM key is configured, a deterministic templated
 * response is used instead so the assistant always works.
 */
const PORT = Number(process.env.PORT || 4021);
const SELF_BASE = `http://localhost:${PORT}`;
const SHIPMENT_ALIASES = [
    { displayId: "CP001", storeId: "CP-CLEAN", scenario: "clean" },
    { displayId: "CP002", storeId: "CP-FRAUD", scenario: "fraud" },
];
function resolveShipmentAlias(raw) {
    const normalized = raw.trim().toUpperCase().replace(/\s+/g, "");
    return (SHIPMENT_ALIASES.find((a) => a.displayId === normalized ||
        a.storeId === normalized.replace(/^CP0*/, "CP-").replace("CP-", "CP-") ||
        normalized === a.storeId ||
        normalized.replace("-", "") === a.storeId.replace("-", "")) || null);
}
/** Matches any CP-style shipment reference, known or not, so unknown IDs
 * (e.g. CP999) can be reported cleanly instead of falling through to
 * generic help. */
function extractRawShipmentToken(message) {
    const match = message.toUpperCase().match(/\bCP[-\s]?[A-Z0-9]{1,10}\b/);
    return match ? match[0] : null;
}
function extractShipmentId(message) {
    const token = extractRawShipmentToken(message);
    if (!token)
        return null;
    return resolveShipmentAlias(token);
}
/** True if the user referenced a CP-style shipment ID that isn't a known one. */
function hasUnknownShipmentReference(message) {
    const token = extractRawShipmentToken(message);
    return Boolean(token) && !resolveShipmentAlias(token);
}
function mentionsTransaction(message) {
    return /transaction|\btx\b/i.test(message);
}
function extractTransactionId(message) {
    // Algorand tx ids are 52-char base32; scan tokens for one.
    const tokens = message.match(/[A-Za-z2-7]{52}/g) || [];
    const valid = tokens.find((t) => isValidAlgorandTxId(t));
    return valid ? valid.toUpperCase() : null;
}
function detectIntent(message, shipment, txId) {
    const m = message.toLowerCase();
    if (txId)
        return "TRANSACTION_LOOKUP";
    // User clearly wants a transaction explained but gave something that
    // isn't a valid Algorand transaction ID — report a clean validation
    // error rather than falling through to generic help.
    if (mentionsTransaction(message))
        return "TRANSACTION_LOOKUP";
    if (!shipment) {
        if (hasUnknownShipmentReference(message))
            return "SHIPMENT_LOOKUP";
        return "GENERAL_CARGOPROOF_HELP";
    }
    if (/\bverify\b|\bverification\b.*\b(run|start|check)\b/.test(m))
        return "VERIFY_SHIPMENT";
    if (/why|suspicious|reject|fail|what happened|explain/.test(m))
        return "EXPLANATION";
    if (/evidence/.test(m))
        return "EVIDENCE_LOOKUP";
    if (/escrow/.test(m))
        return "ESCROW_LOOKUP";
    if (/payment|cost|how much|price|paid|spend/.test(m))
        return "PAYMENT_LOOKUP";
    if (/check|status|is .* (genuine|real|ok)|verify/.test(m))
        return "VERIFY_SHIPMENT";
    return "SHIPMENT_LOOKUP";
}
// ------------------------------------------------------------
// Backend tool calls (existing systems — never duplicated here)
// ------------------------------------------------------------
async function fetchJson(path, init) {
    const response = await fetch(`${SELF_BASE}${path}`, init);
    if (!response.ok)
        return { ok: false, status: response.status, body: null };
    return { ok: true, status: response.status, body: await response.json() };
}
async function getShipmentBundle(alias) {
    const shipmentRes = await fetchJson(`/api/v1/shipments/${alias.storeId}`);
    if (!shipmentRes.ok) {
        return null;
    }
    const shipment = shipmentRes.body;
    const [vesselRes, containerRes] = await Promise.all([
        shipment?.vessel_imo
            ? fetchJson(`/api/v1/vessels/${shipment.vessel_imo}`)
            : Promise.resolve({ ok: false, body: null }),
        shipment?.container_number
            ? fetchJson(`/api/v1/containers/${shipment.container_number}`)
            : Promise.resolve({ ok: false, body: null }),
    ]);
    return {
        displayId: alias.displayId,
        storeId: alias.storeId,
        shipment,
        vessel: vesselRes.ok ? vesselRes.body : null,
        container: containerRes.ok ? containerRes.body : null,
    };
}
async function getCurrentState() {
    const res = await fetchJson("/api/state");
    return res.ok ? res.body : null;
}
/** Triggers the EXISTING verification pipeline (x402 payments + engine). */
async function runVerification(alias) {
    const res = await fetchJson("/api/reset", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scenario: alias.scenario }),
    });
    return res.ok ? res.body : null;
}
/**
 * Ensures the live backend `state` reflects the requested shipment before
 * we read escrow/evidence/payment info from it. Only re-runs verification
 * (which may trigger real x402 payments) when the current state doesn't
 * already correspond to this shipment.
 */
async function ensureStateFor(alias) {
    const current = await getCurrentState();
    if (current && current.scenario === alias.scenario && (current.events || []).length > 0) {
        return current;
    }
    return runVerification(alias);
}
function extractLatestTxFromEvidence(evidence) {
    for (const item of evidence || []) {
        const raw = item?.txId;
        if (!raw)
            continue;
        try {
            const decoded = JSON.parse(Buffer.from(raw, "base64").toString("utf-8"));
            if (decoded?.transaction)
                return decoded.transaction;
        }
        catch {
            // txId wasn't a base64 PAYMENT-RESPONSE envelope (e.g. demo mode) — skip
        }
    }
    return null;
}
// ------------------------------------------------------------
// Response builders per intent
// ------------------------------------------------------------
async function handleTransactionLookup(message, txId) {
    if (!txId) {
        return {
            message: "That doesn't look like a valid Algorand Testnet transaction ID. Transaction IDs are 52-character values using only letters A-Z and digits 2-7. Please double-check the ID and try again.",
            intent: "TRANSACTION_LOOKUP",
            transaction: null,
            lora_url: null,
            error: "INVALID_TRANSACTION_ID",
        };
    }
    let raw;
    try {
        raw = await getTransaction(txId);
    }
    catch (error) {
        return {
            message: "That doesn't look like a valid Algorand Testnet transaction ID. Transaction IDs are 52-character values using letters A-Z and digits 2-7.",
            intent: "TRANSACTION_LOOKUP",
            transaction: null,
            lora_url: null,
            error: "INVALID_TRANSACTION_ID",
        };
    }
    if (!raw) {
        return {
            message: `I couldn't find a transaction with ID ${txId} on Algorand Testnet. It may not exist, may still be propagating, or may be on a different network.`,
            intent: "TRANSACTION_LOOKUP",
            transaction: null,
            lora_url: buildLoraTestnetTxUrl(txId),
        };
    }
    const summary = summarizeTransaction(raw, txId);
    const loraUrl = buildLoraTestnetTxUrl(txId);
    // Try to classify against known CargoProof payment amounts (0.20/0.35/0.08 USDC = 200000/350000/80000 microUSDC)
    const knownEvidencePrices = [200000, 350000, 80000];
    const isLikelyEvidencePayment = summary.assetTransfer &&
        knownEvidencePrices.includes(summary.assetTransfer.amount);
    const classification = isLikelyEvidencePayment
        ? "This appears to be an x402 evidence payment made by CargoProof to an evidence provider (amount matches a known CargoProof provider price)."
        : summary.applicationCall
            ? "This is an application call — it may relate to CargoProof's escrow smart contract, but the app ID should be checked against the configured ESCROW_APP_ID to confirm."
            : "This transaction's purpose could not be conclusively matched to a known CargoProof payment.";
    const structured = { transaction: summary, classification, lora_url: loraUrl };
    const fallback = [
        `Transaction: ${summary.id}`,
        `Status: ${summary.status}`,
        summary.confirmedRound ? `Confirmed round: ${summary.confirmedRound}` : null,
        summary.sender ? `Sender: ${summary.sender}` : null,
        summary.assetTransfer
            ? `Asset transfer: asset ${summary.assetTransfer.assetId}, amount ${summary.assetTransfer.amount}, receiver ${summary.assetTransfer.receiver}`
            : null,
        summary.payment
            ? `Payment: ${summary.payment.amount} microAlgo to ${summary.payment.receiver}`
            : null,
        classification,
        `View on Lora: ${loraUrl}`,
    ]
        .filter(Boolean)
        .join("\n");
    const llm = await explainWithLLM(message, structured, fallback);
    return {
        message: llm.text,
        intent: "TRANSACTION_LOOKUP",
        transaction: summary,
        lora_url: loraUrl,
    };
}
async function handleShipmentLookup(message, alias) {
    if (!alias) {
        const token = extractRawShipmentToken(message);
        return {
            message: `I couldn't find shipment ${token || "that ID"} in CargoProof's data. Known shipments are CP001 and CP002.`,
            intent: "SHIPMENT_LOOKUP",
            shipment_id: token,
            shipment: null,
        };
    }
    const bundle = await getShipmentBundle(alias);
    if (!bundle || !bundle.shipment) {
        return {
            message: `I couldn't find shipment ${alias.displayId} in CargoProof's data. Known shipments are CP001 and CP002.`,
            intent: "SHIPMENT_LOOKUP",
            shipment_id: alias.displayId,
            shipment: null,
        };
    }
    const currentState = await getCurrentState();
    const stateMatches = currentState?.scenario === alias.scenario;
    const structured = {
        shipment_id: bundle.displayId,
        internal_id: bundle.storeId,
        shipment: bundle.shipment,
        vessel: bundle.vessel,
        container: bundle.container,
        current_run_state: stateMatches ? currentState : null,
    };
    const fallback = [
        `Shipment ${bundle.displayId} (${bundle.storeId})`,
        `Vessel: ${bundle.vessel?.name || "unknown"} (${bundle.shipment.vessel_imo})`,
        `Container: ${bundle.shipment.container_number}`,
        `Route: ${bundle.shipment.origin_port} -> ${bundle.shipment.destination_port}`,
        `Claimed status: ${bundle.shipment.claimed_status}`,
        `Declared value: ${bundle.shipment.declared_value}`,
        stateMatches
            ? `Latest verification run: escrow ${currentState.escrow}, confidence ${Math.round((currentState.confidence || 0) * 100)}%`
            : "No verification has been run for this shipment yet in the current session.",
    ].join("\n");
    const llm = await explainWithLLM(message, structured, fallback);
    return {
        message: llm.text,
        intent: "SHIPMENT_LOOKUP",
        shipment_id: bundle.displayId,
        shipment: structured.shipment,
        vessel: structured.vessel,
        container: structured.container,
    };
}
async function handleVerify(message, alias) {
    const result = await runVerification(alias);
    if (!result) {
        return {
            message: "I couldn't reach the CargoProof backend to run verification. Make sure the CargoProof server is running on port " +
                PORT +
                ".",
            intent: "VERIFY_SHIPMENT",
            shipment_id: alias.displayId,
            verification: null,
        };
    }
    const settlementTx = extractLatestTxFromEvidence(result.evidence);
    const structured = {
        shipment_id: alias.displayId,
        escrow: result.escrow,
        confidence: result.confidence,
        spend_usd: result.spendUsd,
        evidence: result.evidence,
        events: result.events?.slice(0, 12),
        settlement_transaction: settlementTx,
        lora_url: settlementTx ? buildLoraTestnetTxUrl(settlementTx) : null,
    };
    const verdict = result.escrow === "RELEASED" ? "VERIFIED" : "SUSPICIOUS / HELD";
    const fallback = [
        `${alias.displayId} — ${verdict}`,
        `Confidence: ${Math.round((result.confidence || 0) * 100)}%`,
        `Evidence purchased: ${(result.evidence || [])
            .map((e) => `${e.provider} ($${e.priceUsd})`)
            .join(", ")}`,
        `Total spent: $${result.spendUsd?.toFixed?.(2) ?? result.spendUsd}`,
        `Escrow: ${result.escrow}`,
        settlementTx ? `Payment transaction: ${settlementTx}` : null,
        settlementTx ? `View on Lora: ${buildLoraTestnetTxUrl(settlementTx)}` : null,
    ]
        .filter(Boolean)
        .join("\n");
    const llm = await explainWithLLM(message, structured, fallback);
    return {
        message: llm.text,
        intent: "VERIFY_SHIPMENT",
        shipment_id: alias.displayId,
        verification: {
            status: verdict,
            confidence: result.confidence,
            decision: result.escrow === "RELEASED" ? "RELEASE" : "DO_NOT_RELEASE",
        },
        payments: result.evidence,
        transactions: settlementTx ? [{ id: settlementTx, lora_url: buildLoraTestnetTxUrl(settlementTx) }] : [],
        escrow: { status: result.escrow },
    };
}
async function handleExplanation(message, alias) {
    const state = await ensureStateFor(alias);
    if (!state) {
        return {
            message: "I couldn't reach the CargoProof backend to explain this shipment.",
            intent: "EXPLANATION",
            shipment_id: alias.displayId,
        };
    }
    const decisionEvent = (state.events || []).find((e) => e.type === "DECISION" && e.failedRules);
    const structured = {
        shipment_id: alias.displayId,
        escrow: state.escrow,
        confidence: state.confidence,
        failed_rules: decisionEvent?.failedRules || [],
        warnings: decisionEvent?.warnings || [],
        evidence: state.evidence,
    };
    const fallback = state.escrow === "RELEASED"
        ? `${alias.displayId} is VERIFIED. The verification engine found no material rule failures, so the decision was RELEASE and escrow moved to RELEASED.`
        : `${alias.displayId} is currently classified as SUSPICIOUS/HELD.\n\nThe verification engine found:\n${(decisionEvent?.failedRules || [])
            .map((r) => `✗ ${r.rule}: ${r.message}`)
            .join("\n") || "a material conflict in the collected evidence"}\n\nBecause verification did not pass, escrow remains HELD.`;
    const llm = await explainWithLLM(message, structured, fallback);
    return {
        message: llm.text,
        intent: "EXPLANATION",
        shipment_id: alias.displayId,
        verification: { escrow: state.escrow, confidence: state.confidence, failed_rules: structured.failed_rules },
    };
}
async function handleEvidenceLookup(message, alias) {
    const state = await ensureStateFor(alias);
    if (!state) {
        return { message: "Couldn't reach the CargoProof backend.", intent: "EVIDENCE_LOOKUP", shipment_id: alias.displayId };
    }
    const structured = { shipment_id: alias.displayId, evidence: state.evidence };
    const fallback = (state.evidence || [])
        .map((e) => `${e.provider}: ${e.observed} (paid $${e.priceUsd}, ${e.simulated ? "simulated source" : "live source"})`)
        .join("\n") || "No evidence has been collected yet for this shipment.";
    const llm = await explainWithLLM(message, structured, fallback);
    return { message: llm.text, intent: "EVIDENCE_LOOKUP", shipment_id: alias.displayId, evidence: state.evidence };
}
async function handlePaymentLookup(message, alias) {
    const state = await ensureStateFor(alias);
    if (!state) {
        return { message: "Couldn't reach the CargoProof backend.", intent: "PAYMENT_LOOKUP", shipment_id: alias.displayId };
    }
    const settlementTx = extractLatestTxFromEvidence(state.evidence);
    const structured = {
        shipment_id: alias.displayId,
        total_spend_usd: state.spendUsd,
        payments: (state.evidence || []).map((e) => ({ provider: e.provider, price_usd: e.priceUsd, tx_id: e.txId })),
        latest_settlement_tx: settlementTx,
    };
    const fallback = `Total evidence cost for ${alias.displayId}: $${state.spendUsd?.toFixed?.(2) ?? state.spendUsd}. ${(state.evidence || [])
        .map((e) => `${e.provider} cost $${e.priceUsd}`)
        .join("; ")}`;
    const llm = await explainWithLLM(message, structured, fallback);
    return {
        message: llm.text,
        intent: "PAYMENT_LOOKUP",
        shipment_id: alias.displayId,
        payments: structured.payments,
        transactions: settlementTx ? [{ id: settlementTx, lora_url: buildLoraTestnetTxUrl(settlementTx) }] : [],
    };
}
async function handleEscrowLookup(message, alias) {
    const state = await ensureStateFor(alias);
    if (!state) {
        return { message: "Couldn't reach the CargoProof backend.", intent: "ESCROW_LOOKUP", shipment_id: alias.displayId };
    }
    const structured = { shipment_id: alias.displayId, escrow: state.escrow, protected_value_inr: state.protectedValueInr };
    const fallback = state.escrow === "RELEASED"
        ? `Escrow for ${alias.displayId} is RELEASED. Funds moved after the verification engine approved the claim.`
        : state.escrow === "HELD"
            ? `Escrow for ${alias.displayId} is HELD. Funds remain protected until the claim is resolved.`
            : `Escrow for ${alias.displayId} is PENDING — verification hasn't completed yet.`;
    const llm = await explainWithLLM(message, structured, fallback);
    return { message: llm.text, intent: "ESCROW_LOOKUP", shipment_id: alias.displayId, escrow: { status: state.escrow } };
}
async function handleGeneralHelp(message) {
    const structured = {
        capabilities: [
            "Verify CP001 / CP002",
            "Show shipment, evidence, payment, and escrow details",
            "Explain why a shipment is VERIFIED or SUSPICIOUS",
            "Look up any Algorand Testnet transaction ID",
        ],
    };
    const fallback = "I'm the CargoProof Assistant. Ask me things like \"Verify CP001\", \"Why is CP002 suspicious?\", \"Show evidence for CP001\", \"What is the escrow status?\", or paste an Algorand transaction ID to have it explained.";
    const llm = await explainWithLLM(message, structured, fallback);
    return { message: llm.text, intent: "GENERAL_CARGOPROOF_HELP" };
}
// ------------------------------------------------------------
// Input validation
// ------------------------------------------------------------
function sanitizeMessage(input) {
    if (typeof input !== "string")
        return null;
    const trimmed = input.trim();
    if (!trimmed || trimmed.length > 2000)
        return null;
    return trimmed;
}
// ------------------------------------------------------------
// Router
// ------------------------------------------------------------
export const chatApi = new Hono();
chatApi.post("/api/v1/chat", async (c) => {
    const body = await c.req.json().catch(() => null);
    const message = sanitizeMessage(body?.message);
    if (!message) {
        return c.json({ message: "Please send a non-empty message (max 2000 characters).", intent: "GENERAL_CARGOPROOF_HELP" }, 400);
    }
    const shipment = extractShipmentId(message);
    const txId = extractTransactionId(message);
    const intent = detectIntent(message, shipment, txId);
    try {
        switch (intent) {
            case "TRANSACTION_LOOKUP":
                return c.json(await handleTransactionLookup(message, txId));
            case "VERIFY_SHIPMENT":
                return c.json(await handleVerify(message, shipment));
            case "EXPLANATION":
                return c.json(await handleExplanation(message, shipment));
            case "EVIDENCE_LOOKUP":
                return c.json(await handleEvidenceLookup(message, shipment));
            case "PAYMENT_LOOKUP":
                return c.json(await handlePaymentLookup(message, shipment));
            case "ESCROW_LOOKUP":
                return c.json(await handleEscrowLookup(message, shipment));
            case "SHIPMENT_LOOKUP":
                return c.json(await handleShipmentLookup(message, shipment));
            default:
                return c.json(await handleGeneralHelp(message));
        }
    }
    catch (error) {
        console.error("[chatbot] error", error);
        return c.json({
            message: "Something went wrong while processing that request against the CargoProof backend.",
            intent,
            error: String(error?.message || error),
        }, 500);
    }
});
