import "dotenv/config";

import { evidenceApi } from "./services/evidenceApi.js";
import { chatApi } from "./services/chatApi.js";

import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { cors } from "hono/cors";

import {
  paymentMiddleware,
  x402ResourceServer,
} from "@x402/hono";

import {
  HTTPFacilitatorClient,
  type RoutesConfig,
} from "@x402/core/server";

import {
  ALGORAND_TESTNET_CAIP2,
  ALGORAND_TESTNET_GENESIS_HASH,
  USDC_TESTNET_ASA_ID,
  toClientAvmSigner,
} from "@x402/avm";

import { ExactAvmScheme as ServerExactAvmScheme } from "@x402/avm/exact/server";
import { ExactAvmScheme } from "@x402/avm/exact/client";

import { x402Client } from "@x402/core/client";
import { wrapFetchWithPayment } from "@x402/fetch";


// ============================================================
// APP
// ============================================================

export const app = new Hono();

app.use("*", cors());

app.route("/", evidenceApi);
app.route("/", chatApi);


// ============================================================
// CONFIG
// ============================================================

const PORT = Number(process.env.PORT || 4021);

const DEMO_MODE =
  (process.env.DEMO_MODE || "true").toLowerCase() === "true";

const PAY_TO = process.env.PAY_TO;

const FACILITATOR_URL =
  process.env.FACILITATOR_URL ||
  "https://facilitator.goplausible.xyz";

const VERIFICATION_ENGINE_URL =
  process.env.VERIFICATION_ENGINE_URL ||
  "http://127.0.0.1:8001";

const X402_ALGORAND_TESTNET_NETWORK =
  `algorand:${ALGORAND_TESTNET_GENESIS_HASH}`;


// ============================================================
// TYPES
// ============================================================

type Scenario = "fraud" | "clean";

type EscrowStatus =
  | "PENDING"
  | "HELD"
  | "RELEASED";

type VerificationReport = {
  verification_status:
    | "VERIFIED"
    | "HOLD"
    | "REJECTED";

  confidence_score: number;

  decision:
    | "RELEASE"
    | "DO_NOT_RELEASE";

  evidence_hash: string;

  failed_rules: {
    rule: string;
    severity: string;
    message: string;
  }[];

  warnings: string[];
};


// ============================================================
// STATE
// ============================================================

const state = {
  scenario: "fraud" as Scenario,

  escrow: "PENDING" as EscrowStatus,

  confidence: 0,

  protectedValueInr: 5_000_000,

  spendUsd: 0,

  evidence: [] as any[],

  events: [] as any[],

  startedAt: new Date().toISOString(),
};


// ============================================================
// EVENT LOGGER
// ============================================================

function event(
  type: string,
  message: string,
  data: any = {}
) {
  const item = {
    id: crypto.randomUUID(),

    time: new Date().toISOString(),

    type,

    message,

    ...data,
  };

  state.events.unshift(item);

  return item;
}


// ============================================================
// RESET
// ============================================================

function reset(scenario: Scenario) {
  state.scenario = scenario;

  state.escrow = "PENDING";

  state.confidence = 0.50;

  state.spendUsd = 0;

  state.evidence = [];

  state.events = [];

  state.startedAt = new Date().toISOString();

  event(
    "SYSTEM",
    `Started ${scenario} shipment verification`
  );
}


// ============================================================
// VERIFICATION ENGINE
// ============================================================

async function callVerificationEngine(
  shipmentId: string
): Promise<VerificationReport | null> {
  try {
    const response = await fetch(
      `${VERIFICATION_ENGINE_URL}/api/v1/verify`,
      {
        method: "POST",

        headers: {
          "content-type": "application/json",
        },

        body: JSON.stringify({
          shipment_id: shipmentId,
        }),
      }
    );

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as VerificationReport;
  } catch {
    return null;
  }
}


// ============================================================
// x402 FACILITATOR / RESOURCE SERVER
// ============================================================

const facilitator =
  new HTTPFacilitatorClient({
    url: FACILITATOR_URL,
  });

const resourceServer =
  new x402ResourceServer(
    facilitator
  );

resourceServer.register(
  X402_ALGORAND_TESTNET_NETWORK,
  new ServerExactAvmScheme()
);


// ============================================================
// x402 PAYMENT ROUTES
// ============================================================

const x402Routes: RoutesConfig = {
  "POST /providers/ais/query": {
    accepts: {
      scheme: "exact",

      network: X402_ALGORAND_TESTNET_NETWORK,

      payTo: PAY_TO!,

      price: "$0.20",

      maxTimeoutSeconds: 120,

      extra: {
        asset: USDC_TESTNET_ASA_ID,
      },
    },

    description:
      "CargoProof AIS evidence query",

    mimeType:
      "application/json",
  },

  "POST /providers/port/query": {
    accepts: {
      scheme: "exact",

      network: X402_ALGORAND_TESTNET_NETWORK,

      payTo: PAY_TO!,

      price: "$0.35",

      maxTimeoutSeconds: 120,

      extra: {
        asset: USDC_TESTNET_ASA_ID,
      },
    },

    description:
      "CargoProof port-arrival evidence query",

    mimeType:
      "application/json",
  },

  "POST /providers/document/query": {
    accepts: {
      scheme: "exact",

      network: X402_ALGORAND_TESTNET_NETWORK,

      payTo: PAY_TO!,

      price: "$0.08",

      maxTimeoutSeconds: 120,

      extra: {
        asset: USDC_TESTNET_ASA_ID,
      },
    },

    description:
      "CargoProof document consistency evidence query",

    mimeType:
      "application/json",
  },
};


// ============================================================
// x402 SERVER MIDDLEWARE
// ============================================================

if (!DEMO_MODE) {
  if (!process.env.PAY_TO) {
    throw new Error(
      "PAY_TO must be configured when DEMO_MODE=false"
    );
  }

  app.use(
    paymentMiddleware(
      x402Routes,
      resourceServer,
      undefined,
      undefined,
      false
    )
  );

  console.log(
    "[x402] REAL PAYMENT MODE ENABLED"
  );

  console.log(
    `[x402] Network: ${ALGORAND_TESTNET_CAIP2}`
  );

  console.log(
    `[x402] USDC ASA: ${USDC_TESTNET_ASA_ID}`
  );

  console.log(
    `[x402] PayTo: ${PAY_TO}`
  );

  console.log(
    `[x402] Facilitator: ${FACILITATOR_URL}`
  );
} else {
  console.log(
    "[x402] DEMO MODE ENABLED - payments bypassed"
  );
}


// ============================================================
// PAID FETCH
// ============================================================

function createPaidFetch() {
  // ----------------------------------------------------------
  // DEMO
  // ----------------------------------------------------------

  if (DEMO_MODE) {
    return fetch;
  }


  // ----------------------------------------------------------
  // REAL MODE
  // ----------------------------------------------------------

  const privateKey =
    process.env.AVM_PRIVATE_KEY_BASE64;

  if (!privateKey) {
    throw new Error(
      "AVM_PRIVATE_KEY_BASE64 missing while DEMO_MODE=false"
    );
  }


  const signer =
    toClientAvmSigner(privateKey);


  console.log(
    `[x402] Client signer: ${signer.address}`
  );


  const client =
    new x402Client();


  client.register(
    X402_ALGORAND_TESTNET_NETWORK,
    new ExactAvmScheme(signer)
  );


  return wrapFetchWithPayment(
    fetch,
    client
  );
}


const paidFetch =
  createPaidFetch();

console.log(
  "[x402] Payment-enabled fetch initialized"
);

console.log(
  "[x402] Network:",
  ALGORAND_TESTNET_CAIP2
);

console.log(
  "[x402] USDC ASA:",
  USDC_TESTNET_ASA_ID
);

// ============================================================
// HEALTH
// ============================================================

app.get(
  "/api/health",
  (c) =>
    c.json({
      ok: true,

      name: "CargoProof",

      demoMode: DEMO_MODE,

      network:
        ALGORAND_TESTNET_CAIP2,

      usdcAsset:
        USDC_TESTNET_ASA_ID,
    })
);


// ============================================================
// STATE
// ============================================================

app.get(
  "/api/state",
  (c) =>
    c.json({
      ...state,

      network:
        ALGORAND_TESTNET_CAIP2,

      usdcAsset:
        USDC_TESTNET_ASA_ID,

      payToConfigured:
        Boolean(process.env.PAY_TO),

      payTo:
        process.env.PAY_TO || null,

      facilitator:
        FACILITATOR_URL,

      escrowAppId:
        process.env.ESCROW_APP_ID || null,
    })
);


// ============================================================
// PROVIDER REGISTRY
// ============================================================

app.get(
  "/api/providers",
  async (c) => {
    const providers = [
      {
        id: "ais-dubai-demo",

        name:
          "AIS Intelligence Provider",

        type: "ais",

        priceUsd: 0.20,

        confidence: 0.91,

        endpoint:
          "/providers/ais/query",
      },

      {
        id: "port-dubai-demo",

        name:
          "Port Arrival Provider",

        type: "port",

        priceUsd: 0.35,

        confidence: 0.95,

        endpoint:
          "/providers/port/query",
      },

      {
        id: "doc-consistency-demo",

        name:
          "Document Consistency Provider",

        type: "document",

        priceUsd: 0.08,

        confidence: 0.80,

        endpoint:
          "/providers/document/query",
      },
    ];

    return c.json(providers);
  }
);


// ============================================================
// AIS PROVIDER
// ============================================================

app.post(
  "/providers/ais/query",
  async (c) => {
    const scenario =
      state.scenario;


    if (scenario === "fraud") {
      return c.json({
        provider:
          "AIS Intelligence Provider",

        observed:
          "Vessel last position 38 km offshore Dubai; no port entry recorded.",

        vesselStatus:
          "OFFSHORE",

        arrivalConfirmed:
          false,

        sourceType:
          "synthetic_ais",

        simulated:
          true,
      });
    }


    return c.json({
      provider:
        "AIS Intelligence Provider",

      observed:
        "Vessel entered Dubai approach and docked within the claimed window.",

      vesselStatus:
        "DOCKED",

      arrivalConfirmed:
        true,

      sourceType:
        "synthetic_ais",

      simulated:
        true,
    });
  }
);


// ============================================================
// PORT PROVIDER
// ============================================================

app.post(
  "/providers/port/query",
  async (c) => {
    const scenario =
      state.scenario;


    if (scenario === "fraud") {
      return c.json({
        provider:
          "Port Arrival Provider",

        observed:
          "No arrival record found for the vessel in the previous 72 hours.",

        arrivalConfirmed:
          false,

        sourceType:
          "synthetic_port_record",

        simulated:
          true,
      });
    }


    return c.json({
      provider:
        "Port Arrival Provider",

      observed:
        "Arrival and berth record found for the vessel in the claimed window.",

      arrivalConfirmed:
        true,

      sourceType:
        "synthetic_port_record",

      simulated:
        true,
    });
  }
);


// ============================================================
// DOCUMENT PROVIDER
// ============================================================

app.post(
  "/providers/document/query",
  async (c) => {
    const scenario =
      state.scenario;


    return c.json({
      provider:
        "Document Consistency Provider",

      observed:
        scenario === "fraud"
          ? "Document metadata is internally consistent but does not independently prove physical arrival."
          : "Document fields are internally consistent.",

      consistent:
        true,

      sourceType:
        "synthetic_document_check",

      simulated:
        true,
    });
  }
);


// ============================================================
// AGENT
// ============================================================

async function runAgent(
  scenario: Scenario
) {
  reset(scenario);


  event(
    "AGENT",
    "Parsing shipment claim",
    {
      claim:
        "MV Chennai Star arrived at Dubai Port on Aug 19",

      valueInr:
        state.protectedValueInr,
    }
  );


  event(
    "AGENT",
    "Building evidence plan",
    {
      budgetUsd:
        1.00,

      policy:
        "Buy the cheapest independent evidence that can materially reduce uncertainty.",
    }
  );


  // ==========================================================
  // AIS
  // ==========================================================

  event(
    "PAYMENT_REQUIRED",
    "Requesting AIS evidence",
    {
      priceUsd:
        0.20,
    }
  );


  event(
    "PAYMENT_PROCESSING",
    "x402 client received 402 and is creating the Algorand USDC payment.",
    {
      provider:
        "AIS Intelligence Provider",

      priceUsd:
        0.20,

      network:
        ALGORAND_TESTNET_CAIP2,

      asset:
        USDC_TESTNET_ASA_ID,
    }
  );


  const aisResponse =
    await paidFetch(
      `http://localhost:${PORT}/providers/ais/query`,
      {
        method: "POST",

        headers: {
          "content-type":
            "application/json",
        },

        body: JSON.stringify({
          shipmentId:
            scenario === "clean"
              ? "CP001"
              : "CP002",
        }),
      }
    );

  if (aisResponse.ok) {
    event(
      "PAYMENT_CONFIRMED",
      "x402 payment accepted and the provider released AIS evidence.",
      {
        provider:
          "AIS Intelligence Provider",

        priceUsd:
          0.20,

        paymentResponse:
          aisResponse.headers.get("PAYMENT-RESPONSE"),
      }
    );
  }

  if (!aisResponse.ok) {
    throw new Error(
      `AIS provider failed: HTTP ${aisResponse.status}`
    );
  }


  const aisResponseBody =
    await aisResponse.text();

  const ais =
    JSON.parse(aisResponseBody);


  state.spendUsd += 0.20;


  const aisPaymentResponse =
    aisResponse.headers.get(
      "PAYMENT-RESPONSE"
    );


  state.evidence.push({
    ...ais,

    priceUsd:
      0.20,

    paid:
      true,

    txId:
      aisPaymentResponse || null,
  });


  state.confidence =
    scenario === "fraud"
      ? 0.28
      : 0.84;


  event(
    "EVIDENCE",
    "AIS evidence received",
    {
      confidence:
        state.confidence,

      evidence:
        ais,

      paymentResponse:
        aisPaymentResponse,
    }
  );


  // ==========================================================
  // CLEAN PATH
  // ==========================================================

  if (scenario === "clean") {

    event(
      "DECISION",
      "AIS strongly supports arrival; buying a cheap consistency check."
    );


    event(
      "PAYMENT_REQUIRED",
      "Requesting document consistency evidence",
      {
        priceUsd:
          0.08,
      }
    );


    // Document provider is protected by x402.
    // The agent will automatically pay $0.08
    // when the provider returns HTTP 402.

    const docResponse =
      await paidFetch(
        `http://localhost:${PORT}/providers/document/query`,
        {
          method: "POST",

          headers: {
            "content-type":
              "application/json",
          },

          body: JSON.stringify({
            shipmentId:
              "CP001",
          }),
        }
      );


    if (!docResponse.ok) {
      throw new Error(
        `Document provider failed: HTTP ${docResponse.status}`
      );
    }


    const doc =
      await docResponse.json();


    state.spendUsd += 0.08;


    const docPaymentResponse =
      docResponse.headers.get(
        "PAYMENT-RESPONSE"
      );


    state.evidence.push({
      ...doc,

      priceUsd:
        0.08,

      paid:
        true,

      txId:
        docPaymentResponse || null,
    });


  } else {

    // ========================================================
    // FRAUD PATH
    // ========================================================

    event(
      "AGENT",
      "AIS contradicts the submitted document. Purchasing independent port evidence."
    );


    event(
      "PAYMENT_REQUIRED",
      "Requesting port arrival evidence",
      {
        priceUsd:
          0.35,
      }
    );

    event(
      "PAYMENT_PROCESSING",
      "x402 client received 402 and is creating the Algorand USDC payment.",
      {
        provider:
          "Port Intelligence Provider",

        priceUsd:
          0.35,

        network:
          ALGORAND_TESTNET_CAIP2,

        asset:
          USDC_TESTNET_ASA_ID,
      }
    );

    const portResponse =
      await paidFetch(
        `http://localhost:${PORT}/providers/port/query`,
        {
          method: "POST",

          headers: {
            "content-type":
              "application/json",
          },

          body: JSON.stringify({
            shipmentId:
              "CP002",
          }),
        }
      );

      if (portResponse.ok) {
        event(
          "PAYMENT_CONFIRMED",
          "x402 payment accepted and the provider released port evidence.",
          {
            provider:
              "Port Intelligence Provider",

            priceUsd:
              0.35,

            paymentResponse:
              portResponse.headers.get("PAYMENT-RESPONSE"),
          }
        );
      }

    if (!portResponse.ok) {
      throw new Error(
        `Port provider failed: HTTP ${portResponse.status}`
      );
    }


    const port =
      await portResponse.json();


    state.spendUsd += 0.35;


    const portPaymentResponse =
      portResponse.headers.get(
        "PAYMENT-RESPONSE"
      );


    state.evidence.push({
      ...port,

      priceUsd:
        0.35,

      paid:
        true,

      txId:
        portPaymentResponse || null,
    });


    event(
      "EVIDENCE",
      "Port evidence received",
      {
        evidence:
          port,

        paymentResponse:
          portPaymentResponse,
      }
    );
  }


  // ==========================================================
  // VERIFICATION ENGINE
  // ==========================================================

  const shipmentId =
    scenario === "clean"
      ? "CP001"
      : "CP002";


  event(
    "AGENT",
    "Requesting verdict from verification engine",
    {
      shipmentId,
    }
  );


  const report =
    await callVerificationEngine(
      shipmentId
    );


  if (report) {

    state.confidence =
      report.confidence_score / 100;


    state.escrow =
      report.decision === "RELEASE"
        ? "RELEASED"
        : "HELD";


    event(
      "DECISION",
      `Verification engine returned ${report.verification_status}. Escrow ${state.escrow}.`,
      {
        confidence:
          state.confidence,

        failedRules:
          report.failed_rules,

        warnings:
          report.warnings,

        engineEvidenceHash:
          report.evidence_hash,
      }
    );

  } else {

    if (scenario === "clean") {

      state.confidence =
        0.97;

      state.escrow =
        "RELEASED";

    } else {

      state.confidence =
        0.12;

      state.escrow =
        "HELD";
    }


    event(
      "DECISION",
      `Verification engine unreachable — using fallback demo logic. Escrow ${state.escrow}.`,
      {
        confidence:
          state.confidence,

        note:
          "Start the verification engine (uvicorn verification_engine.main:app) for real rule-based verdicts.",
      }
    );
  }


  // ==========================================================
  // HASH
  // ==========================================================

  const evidenceHash =
    await sha256(
      JSON.stringify(
        state.evidence
      )
    );


  event(
    "CHAIN",
    "Evidence bundle committed",
    {
      evidenceHash,

      escrow:
        state.escrow,
    }
  );


  return {
    scenario,

    escrow:
      state.escrow,

    confidence:
      state.confidence,

    spendUsd:
      state.spendUsd,

    protectedValueInr:
      state.protectedValueInr,

    evidence:
      state.evidence,

    events:
      state.events,
  };
}


// ============================================================
// RESET / RUN
// ============================================================

app.post(
  "/api/reset",
  async (c) => {

    const body =
      await c.req
        .json()
        .catch(() => ({}));


    const scenario: Scenario =
      body.scenario === "clean"
        ? "clean"
        : "fraud";


    return c.json(
      await runAgent(
        scenario
      )
    );
  }
);


// ============================================================
// SHA256
// ============================================================

async function sha256(
  value: string
) {
  const bytes =
    new TextEncoder().encode(
      value
    );


  const hash =
    await crypto.subtle.digest(
      "SHA-256",
      bytes
    );


  return Array.from(
    new Uint8Array(hash)
  )
    .map((b) =>
      b.toString(16).padStart(2, "0")
    )
    .join("");
}


// ============================================================
// ROOT
// ============================================================

app.get(
  "/",
  (c) =>
    c.redirect("/api/state")
);


// ============================================================
// SERVER
// ============================================================

async function startServer() {
  if (!DEMO_MODE) {
    console.log("[x402] Initializing facilitator...");
    await resourceServer.initialize();
    console.log("[x402] Facilitator initialization complete");
  }

  serve(
    {
      fetch:
        app.fetch,

      port:
        PORT,
    },

    (info) => {

      console.log(
        `CargoProof API running on http://localhost:${info.port}`
      );

      console.log(
        `DEMO_MODE=${DEMO_MODE}`
      );

      console.log(
        `Network=${ALGORAND_TESTNET_CAIP2}`
      );

      console.log(
        `USDC_ASA=${USDC_TESTNET_ASA_ID}`
      );
    }
  );
}
if (!process.env.VERCEL) {
  startServer().catch((error) => {
    console.error("[SERVER STARTUP ERROR]", error);
    process.exit(1);
  });
}