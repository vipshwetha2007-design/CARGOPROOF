import {
    x402Client,
  } from "@x402/core/client";
  
  import {
    ExactAvmScheme,
    toClientAvmSigner,
    ALGORAND_TESTNET_CAIP2,
    ALGORAND_TESTNET_GENESIS_HASH,
  } from "@x402/avm";
  
  export function createCargoProofX402Client() {
    const privateKey = process.env.AVM_PRIVATE_KEY_BASE64;
  
    if (!privateKey) {
      throw new Error(
        "AVM_PRIVATE_KEY_BASE64 is required for live x402 payments"
      );
    }
  
    const signer = toClientAvmSigner(privateKey);
  
    console.log("[x402] Signer address:", signer.address);
  
    const client = new x402Client();
  
    client.register(
      `algorand:${ALGORAND_TESTNET_GENESIS_HASH}`,
      new ExactAvmScheme(signer)
    );
  
    console.log(
      "[x402] Registered Algorand Testnet exact scheme:",
      ALGORAND_TESTNET_CAIP2
    );
  
    return client;
  }