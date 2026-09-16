import "dotenv/config";

import { wrapFetchWithPayment } from "@x402/fetch";
import { x402Client } from "@x402/core/client";

import {
  ExactAvmScheme,
  toClientAvmSigner,
  ALGORAND_TESTNET_CAIP2,
  USDC_TESTNET_ASA_ID,
} from "@x402/avm";


const BASE =
  `http://localhost:${process.env.PORT || 4021}`;


async function main() {

  const privateKey =
    process.env.AVM_PRIVATE_KEY_BASE64;


  if (!privateKey) {
    throw new Error(
      "AVM_PRIVATE_KEY_BASE64 missing"
    );
  }


  const signer =
    toClientAvmSigner(
      privateKey
    );


  console.log(
    "========================================"
  );

  console.log(
    "CargoProof REAL x402 / Algorand client"
  );

  console.log(
    "========================================"
  );

  console.log(
    "Signer:",
    signer.address
  );

  console.log(
    "Network:",
    ALGORAND_TESTNET_CAIP2
  );

  console.log(
    "USDC ASA:",
    USDC_TESTNET_ASA_ID
  );

  console.log(
    "Endpoint:",
    `${BASE}/providers/ais/query`
  );

  console.log("");


  const client =
    new x402Client();


  client.register(
    ALGORAND_TESTNET_CAIP2,
    new ExactAvmScheme(
      signer
    )
  );


  const fetchWithPayment =
    wrapFetchWithPayment(
      fetch,
      client
    );


  console.log(
    "Requesting AIS provider..."
  );

  console.log(
    "The x402 client will automatically:"
  );

  console.log(
    "  1. Receive HTTP 402"
  );

  console.log(
    "  2. Parse payment requirements"
  );

  console.log(
    "  3. Create Algorand USDC payment"
  );

  console.log(
    "  4. Sign the payment"
  );

  console.log(
    "  5. Send payment signature"
  );

  console.log(
    "  6. Retry the request"
  );

  console.log("");


  const response =
    await fetchWithPayment(
      `${BASE}/providers/ais/query`,
      {
        method: "POST",

        headers: {
          "content-type":
            "application/json",
        },

        body: JSON.stringify({
          shipmentId:
            "CP-CLEAN",
        }),
      }
    );


  console.log("");

  console.log(
    "========================================"
  );

  console.log(
    "FINAL RESPONSE"
  );

  console.log(
    "========================================"
  );

  console.log(
    "Status:",
    response.status
  );

  console.log(
    "OK:",
    response.ok
  );


  const text =
    await response.text();


  console.log(
    "Response:"
  );

  console.log(
    text
  );


  const paymentResponse =
    response.headers.get(
      "PAYMENT-RESPONSE"
    );


  if (paymentResponse) {

    console.log("");

    console.log(
      "PAYMENT-RESPONSE:"
    );

    console.log(
      paymentResponse
    );
  }


  if (!response.ok) {

    throw new Error(
      `x402 request failed: HTTP ${response.status}`
    );
  }


  console.log("");

  console.log(
    "========================================"
  );

  console.log(
    "REAL x402 PAYMENT FLOW COMPLETED"
  );

  console.log(
    "========================================"
  );
}


main().catch(
  (error) => {

    console.error("");

    console.error(
      "x402 payment failed:"
    );

    console.error(
      error
    );

    process.exit(1);
  }
);