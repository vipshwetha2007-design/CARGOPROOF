import { x402Client, } from "@x402/core/client";
import { ExactAvmScheme, toClientAvmSigner, ALGORAND_TESTNET_CAIP2, } from "@x402/avm";
import { wrapFetchWithPayment } from "@x402/fetch";
export function createCargoProofFetch() {
    const privateKey = process.env.AVM_PRIVATE_KEY_BASE64;
    if (!privateKey) {
        throw new Error("AVM_PRIVATE_KEY_BASE64 missing");
    }
    const signer = toClientAvmSigner(privateKey);
    console.log(`[x402] Algorand signer: ${signer.address}`);
    console.log(`[x402] Network: ${ALGORAND_TESTNET_CAIP2}`);
    const client = new x402Client();
    client.register(ALGORAND_TESTNET_CAIP2, new ExactAvmScheme(signer));
    return wrapFetchWithPayment(fetch, client);
}
