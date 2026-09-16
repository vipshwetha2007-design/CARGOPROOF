import "dotenv/config";
import { wrapFetchWithPayment } from "@x402/fetch";
import { createCargoProofX402Client } from "./x402.js";
const PORT = process.env.PORT || "4021";
const BASE = `http://localhost:${PORT}`;
async function postWithX402(client, path, body) {
    const url = `${BASE}${path}`;
    console.log("");
    console.log("════════════════════════════════════════");
    console.log("[AGENT] Requesting paid evidence");
    console.log("[AGENT] URL:", url);
    console.log("════════════════════════════════════════");
    /*
     * Current @x402 API:
     *
     * x402Client does not expose client.fetch().
     * wrapFetchWithPayment() wraps the normal fetch()
     * and automatically handles:
     *
     * HTTP 402
     *     ↓
     * payment requirements
     *     ↓
     * Algorand USDC transaction
     *     ↓
     * signing
     *     ↓
     * PAYMENT-SIGNATURE
     *     ↓
     * retry request
     */
    const fetchWithPayment = wrapFetchWithPayment(fetch, client);
    const response = await fetchWithPayment(url, {
        method: "POST",
        headers: {
            "content-type": "application/json",
        },
        body: JSON.stringify(body),
    });
    console.log("[AGENT] Final HTTP status:", response.status);
    const text = await response.text();
    let data;
    try {
        data = JSON.parse(text);
    }
    catch {
        data = text;
    }
    if (!response.ok) {
        throw new Error(`[x402] Paid request failed (${response.status}): ${JSON.stringify(data)}`);
    }
    return data;
}
async function main() {
    const client = createCargoProofX402Client();
    console.log("");
    console.log("╔══════════════════════════════════════╗");
    console.log("║       CARGOPROOF x402 AGENT          ║");
    console.log("╚══════════════════════════════════════╝");
    /*
     * Reset the CargoProof demo state.
     */
    const resetResponse = await fetch(`${BASE}/api/reset`, {
        method: "POST",
        headers: {
            "content-type": "application/json",
        },
        body: JSON.stringify({
            scenario: process.env.SCENARIO || "fraud",
        }),
    });
    if (!resetResponse.ok) {
        throw new Error(`Failed to reset CargoProof: ${resetResponse.status}`);
    }
    console.log("[AGENT] Scenario reset");
    /*
     * =====================================================
     * REAL x402 PAYMENT
     * =====================================================
     *
     * POST provider
     *      ↓
     * HTTP 402
     *      ↓
     * x402 payment requirements
     *      ↓
     * ExactAvmScheme
     *      ↓
     * Build Algorand USDC transaction
     *      ↓
     * Sign using AVM_PRIVATE_KEY_BASE64
     *      ↓
     * PAYMENT-SIGNATURE
     *      ↓
     * Provider verifies payment
     *      ↓
     * Provider settles payment
     *      ↓
     * Request retried
     *      ↓
     * Evidence returned
     */
    const shipmentId = process.env.SHIPMENT_ID ||
        (process.env.SCENARIO === "clean"
            ? "CP001"
            : "CP002");
    console.log("");
    console.log("[AGENT] Shipment ID:", shipmentId);
    /*
     * =====================================================
     * AIS EVIDENCE
     * =====================================================
     */
    const ais = await postWithX402(client, "/providers/ais/query", {
        shipmentId,
    });
    console.log("");
    console.log("════════════════════════════════════════");
    console.log("[AGENT] AIS EVIDENCE RECEIVED");
    console.log("════════════════════════════════════════");
    console.dir(ais, {
        depth: null,
    });
    /*
     * Determine whether AIS confirms arrival.
     *
     * The provider may use either:
     *   arrival
     * or
     *   arrivalConfirmed
     *
     * Support both so the agent works with
     * the current provider responses.
     */
    const aisArrival = typeof ais === "object" &&
        ais !== null &&
        (("arrival" in ais &&
            Boolean(ais.arrival)) ||
            ("arrivalConfirmed" in ais &&
                Boolean(ais.arrivalConfirmed)));
    /*
     * =====================================================
     * PORT EVIDENCE
     * =====================================================
     *
     * If AIS does not independently confirm arrival,
     * purchase another piece of evidence.
     *
     * This is another REAL x402 payment.
     */
    if (!aisArrival) {
        console.log("");
        console.log("[AGENT] AIS does not support arrival.");
        console.log("[AGENT] Purchasing independent port evidence...");
        const port = await postWithX402(client, "/providers/port/query", {
            shipmentId,
        });
        console.log("");
        console.log("════════════════════════════════════════");
        console.log("[AGENT] PORT EVIDENCE RECEIVED");
        console.log("════════════════════════════════════════");
        console.dir(port, {
            depth: null,
        });
    }
    console.log("");
    console.log("════════════════════════════════════════");
    console.log("[AGENT] x402 evidence procurement complete");
    console.log("════════════════════════════════════════");
}
main().catch((error) => {
    console.error("");
    console.error("╔══════════════════════════════════════╗");
    console.error("║       CARGOPROOF AGENT ERROR         ║");
    console.error("╚══════════════════════════════════════╝");
    console.error(error);
    process.exit(1);
});
