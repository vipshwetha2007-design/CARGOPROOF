import "dotenv/config";

/**
 * LLM provider abstraction for the CargoProof Assistant.
 *
 * IMPORTANT SAFETY NOTE:
 * This module NEVER receives private keys, mnemonics, wallet secrets, or
 * facilitator credentials. Callers must only pass already-fetched,
 * structured, public-safe data (shipment records, verification reports,
 * transaction summaries, escrow state). The LLM's job is limited to
 * phrasing that data in plain language — it is not permitted to invent
 * facts, and prompts explicitly instruct it not to.
 */

type ChatRole = "system" | "user";

type ChatMessage = {
  role: ChatRole;
  content: string;
};

const AI_PROVIDER = (process.env.AI_PROVIDER || "gemini").toLowerCase();
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GROQ_API_KEY = process.env.GROQ_API_KEY || "";
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-2.0-flash";
const GROQ_MODEL = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";

const SYSTEM_PROMPT = `You are the CargoProof Assistant, an explanation layer over a real
shipment verification platform. You are given structured, already-verified
data pulled from CargoProof's backend (shipment records, verification
engine reports, x402 payment/evidence records, escrow state, and Algorand
transaction data).

Rules you must always follow:
- Never invent, guess, or embellish shipment, payment, transaction, or
  escrow facts. Only restate what is present in the structured data you
  are given.
- If a field is missing or null, say it is not available. Do not fill gaps
  with plausible-sounding details.
- Only describe a transaction as an "x402 payment", "escrow deposit", or
  "escrow release" when the structured data explicitly says so. Otherwise
  say the purpose could not be conclusively determined.
- Be concise, factual, and use a professional command-center tone
  consistent with a logistics/fintech verification product.
- Numbers (amounts, confidence scores, rounds) must be copied exactly as
  given, not rounded or changed.`;

async function callGemini(messages: ChatMessage[]): Promise<string> {
  if (!GEMINI_API_KEY) throw new Error("GEMINI_API_KEY not configured");

  const systemMsg = messages.find((m) => m.role === "system");
  const userMsgs = messages.filter((m) => m.role === "user");

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        systemInstruction: systemMsg
          ? { parts: [{ text: systemMsg.content }] }
          : undefined,
        contents: userMsgs.map((m) => ({
          role: "user",
          parts: [{ text: m.content }],
        })),
        generationConfig: {
          temperature: 0.2,
          maxOutputTokens: 700,
        },
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Gemini request failed: ${response.status}`);
  }

  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;

  if (!text) throw new Error("Gemini returned no content");
  return text.trim();
}

async function callGroq(messages: ChatMessage[]): Promise<string> {
  if (!GROQ_API_KEY) throw new Error("GROQ_API_KEY not configured");

  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${GROQ_API_KEY}`,
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      temperature: 0.2,
      max_tokens: 700,
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
  });

  if (!response.ok) {
    throw new Error(`Groq request failed: ${response.status}`);
  }

  const data = await response.json();
  const text = data?.choices?.[0]?.message?.content;

  if (!text) throw new Error("Groq returned no content");
  return text.trim();
}

/**
 * Turn structured backend data into a human-readable explanation.
 * `structuredData` must already be sanitized (no secrets) by the caller.
 * Falls back to a deterministic templated summary if no provider is
 * configured or the call fails, so the assistant never goes silent.
 */
export async function explainWithLLM(
  userMessage: string,
  structuredData: unknown,
  fallback: string
): Promise<{ text: string; usedLLM: boolean; provider: string | null }> {
  const messages: ChatMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
    {
      role: "user",
      content: `User asked: "${userMessage}"\n\nStructured CargoProof backend data (source of truth):\n${JSON.stringify(
        structuredData,
        null,
        2
      )}\n\nWrite a clear, accurate answer using only this data.`,
    },
  ];

  const providers =
    AI_PROVIDER === "groq" ? ["groq", "gemini"] : ["gemini", "groq"];

  for (const provider of providers) {
    try {
      if (provider === "gemini" && GEMINI_API_KEY) {
        return { text: await callGemini(messages), usedLLM: true, provider };
      }
      if (provider === "groq" && GROQ_API_KEY) {
        return { text: await callGroq(messages), usedLLM: true, provider };
      }
    } catch (error) {
      console.error(`[chatbot] ${provider} failed, trying fallback`, error);
      continue;
    }
  }

  return { text: fallback, usedLLM: false, provider: null };
}
