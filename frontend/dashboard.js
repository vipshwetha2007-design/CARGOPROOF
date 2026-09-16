const API = "http://localhost:4021";
const NETWORK = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDe";
const ASSET = "10458941";
const providers = {
  ais: { name: "AIS Intelligence Provider", type: "AIS", purpose: "Vessel movement and arrival evidence", price: 0.20, icon: "◌" },
  port: { name: "Port Arrival Provider", type: "PORT", purpose: "Independent port event corroboration", price: 0.35, icon: "⌁" },
  document: { name: "Document Consistency Provider", type: "DOCUMENT", purpose: "Manifest and claim consistency", price: 0.08, icon: "▤" }
};
let currentState = null;
let selectedScenario = "clean";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const money = (value) => `$${Number(value || 0).toFixed(2)}`;
const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;
const time = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "--:--:--";
const short = (value, length = 18) => value && value.length > length ? `${value.slice(0, length)}...` : value || "Not available";

function eventFor(state, type, provider) {
  return (state.events || []).find((item) => item.type === type && (!provider || item.provider === provider));
}

function paymentRecord(state, providerName) {
  const config = Object.values(providers).find((item) => item.name === providerName);
  const evidence = (state.evidence || []).find((item) => item.provider === providerName);
  const confirmed = eventFor(state, "PAYMENT_CONFIRMED", providerName);
  const processing = eventFor(state, "PAYMENT_PROCESSING", providerName);
  const required = eventFor(state, "PAYMENT_REQUIRED", providerName) || (config ? (state.events || []).find((item) => item.type === "PAYMENT_REQUIRED" && Number(item.priceUsd) === config.price) : null);
  return { evidence, confirmed, processing, required };
}

function decodePayment(value) {
  if (!value) return null;
  try {
    const json = atob(value);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function renderSummary(state) {
  const clean = state.scenario === "clean";
  $("shipId").textContent = clean ? "CP001" : "CP002";
  $("scenarioBadge").textContent = `${clean ? "CLEAN" : "FRAUD"} SCENARIO`;
  $("scenarioBadge").className = `status-chip ${clean ? "success" : "danger"}`;
  $("verificationStatus").textContent = state.escrow === "RELEASED" ? "VERIFIED" : state.escrow === "HELD" ? "REJECTED / HOLD" : "PENDING";
  $("verificationStatus").className = `verdict-value ${state.escrow === "RELEASED" ? "success" : state.escrow === "HELD" ? "danger" : "pending"}`;
  $("decisionText").textContent = state.escrow === "RELEASED" ? "RELEASE · engine approved" : state.escrow === "HELD" ? "DO_NOT_RELEASE · funds protected" : "Awaiting verification run";
  $("confidence").textContent = percent(state.confidence);
  $("confidenceBar").style.width = percent(state.confidence);
  $("escrowState").textContent = state.escrow || "PENDING";
  $("escrowState").className = `escrow-value ${String(state.escrow || "pending").toLowerCase()}`;
  $("escrowMessage").textContent = state.escrow === "RELEASED" ? "Funds released after verified evidence." : state.escrow === "HELD" ? "Funds held while the claim remains unresolved." : "Settlement boundary awaiting engine verdict.";
  $("runStatus").textContent = state.escrow === "RELEASED" ? "Verification complete · release authorized" : state.escrow === "HELD" ? "Verification complete · release blocked" : "Ready for verification";
  $("payTo").textContent = short(state.payTo, 20);
  $("payToFull").textContent = state.payTo || "Not configured";
  $("copyPayTo").dataset.copy = state.payTo || "";
  $("copyPayTo").onclick = () => copyValue(state.payTo, $("copyPayTo"));
  $("evidenceCount").textContent = `${(state.evidence || []).length} SOURCES`;
}

function renderPipeline(state) {
  const events = state.events || [];
  const stages = [
    ["SHIPMENT", "Claim received", "SYSTEM"], ["AGENT", "Plan evidence", "AGENT"], ["x402 PAYMENT", "Provider gate", "PAYMENT_REQUIRED"], ["SIGNED", "USDC authorization", "PAYMENT_PROCESSING"], ["SETTLED", "Facilitator accepted", "PAYMENT_CONFIRMED"], ["EVIDENCE", "Provider response", "EVIDENCE"], ["ENGINE", "Rule evaluation", "DECISION"], ["ESCROW", state.escrow === "RELEASED" ? "Release" : state.escrow === "HELD" ? "Hold" : "Pending", "DECISION"]
  ];
  $("pipelineNodes").innerHTML = stages.map(([label, detail, type], index) => {
    const matched = events.find((item) => item.type === type);
    const done = index === 0 ? events.length > 0 : Boolean(matched) || (index === 7 && state.escrow !== "PENDING");
    const tone = type === "DECISION" && state.escrow === "HELD" ? "danger" : done ? "success" : "waiting";
    return `<div class="pipeline-node ${tone}"><div class="node-icon">${done ? "✓" : String(index + 1).padStart(2, "0")}</div><div><strong>${esc(label)}</strong><span>${esc(detail)}</span>${matched ? `<small>${time(matched.time)}</small>` : ""}</div></div>${index < stages.length - 1 ? `<div class="pipeline-link ${done ? "active" : ""}"></div>` : ""}`;
  }).join("");
}

function providerCard(state, key) {
  const config = providers[key];
  const record = paymentRecord(state, config.name);
  const evidence = record.evidence;
  const active = Boolean(record.required || evidence);
  const tx = decodePayment(record.confirmed?.paymentResponse || evidence?.txId);
  const status = evidence ? "SETTLED" : record.required ? "PROCESSING" : "NOT REQUESTED";
  const response = evidence?.observed || "Waiting for this provider in the current decision path.";
  return `<article class="provider-card ${active ? "active" : ""}"><div class="provider-top"><div class="provider-identity"><span class="provider-icon">${config.icon}</span><div><span class="provider-type">${config.type} PROVIDER</span><h3>${esc(config.name)}</h3></div></div><span class="provider-status ${evidence ? "success" : record.required ? "processing" : "neutral"}">${status}</span></div><p class="provider-purpose">${esc(config.purpose)}</p><div class="provider-facts"><div><span>PRICE</span><strong>${money(config.price)}</strong></div><div><span>AMOUNT</span><strong>${Math.round(config.price * 1000000)}</strong></div><div><span>HTTP</span><strong>${record.required ? "402 → 200" : "—"}</strong></div><div><span>SCHEME</span><strong>exact</strong></div><div><span>ASSET</span><strong>USDC</strong></div></div><div class="mini-flow"><span class="flow-done">REQUEST</span><i>→</i><span class="${record.required ? "flow-done" : ""}">402 REQUIRED</span><i>→</i><span class="${record.processing ? "flow-done" : ""}">SIGNED</span><i>→</i><span class="${record.confirmed ? "flow-done" : ""}">SETTLED</span><i>→</i><span class="${evidence ? "flow-done" : ""}">EVIDENCE</span></div><div class="provider-response"><span>LAST RESPONSE</span><p>${esc(response)}</p></div>${tx?.transaction ? `<div class="provider-tx"><span>SETTLEMENT TX</span><code>${esc(short(tx.transaction, 26))}</code><button class="copy-btn" data-copy="${esc(tx.transaction)}">COPY</button></div>` : ""}</article>`;
}

function renderProviders(state) {
  $("providerGrid").innerHTML = Object.keys(providers).map((key) => providerCard(state, key)).join("");
  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", () => copyValue(button.dataset.copy, button)));
}

function renderTimeline(state) {
  const icons = { SYSTEM: "⌂", AGENT: "◇", PAYMENT_REQUIRED: "402", PAYMENT_PROCESSING: "↗", PAYMENT_CONFIRMED: "✓", EVIDENCE: "◉", DECISION: "!", CHAIN: "#" };
  $("timeline").innerHTML = (state.events || []).map((item) => `<div class="stream-row"><time>${time(item.time)}</time><span class="stream-icon">${icons[item.type] || "·"}</span><div><strong>${esc(item.type.replaceAll("_", " "))}</strong><p>${esc(item.message)}</p></div></div>`).join("") || `<div class="empty-state">No events yet. Run a scenario to begin.</div>`;
}

function renderRules(state) {
  const decision = (state.events || []).find((item) => item.type === "DECISION" && item.failedRules);
  const failed = new Map((decision?.failedRules || []).map((rule) => [rule.rule, rule]));
  const names = ["VESSEL_CONTAINER_MATCH", "PORT_EVENT_CONSISTENCY", "DATA_FRESHNESS", "DOCUMENT_CONSISTENCY", "GPS_CONSISTENCY", "INSPECTION"];
  $("rulesList").innerHTML = names.map((name) => { const rule = failed.get(name); return `<div class="rule-row ${rule ? "fail" : "pass"}"><span class="rule-symbol">${rule ? "×" : "✓"}</span><div><strong>${name}</strong><span>${rule ? esc(rule.message) : "PASS · evidence is consistent"}</span></div><b>${rule ? rule.severity : "PASS"}</b></div>`; }).join("");
  $("engineHash").textContent = decision?.engineEvidenceHash || "Awaiting report";
}

function renderEvidence(state) {
  $("evidenceList").innerHTML = (state.evidence || []).map((item) => `<details class="evidence-row"><summary><span class="evidence-marker">✓</span><span><strong>${esc(item.provider)}</strong><small>${item.sourceType ? esc(item.sourceType) : "Provider evidence"}</small></span><b>${money(item.priceUsd)}</b></summary><div class="evidence-detail"><p>${esc(item.observed || "Evidence received")}</p><div class="evidence-meta"><span>${item.paid ? "x402 PAID" : "UNPAID"}</span><span>${item.simulated ? "SIMULATED DOMAIN DATA" : "LIVE SOURCE"}</span>${item.txId ? `<code>${esc(short(item.txId, 30))}</code>` : ""}</div><pre>${esc(JSON.stringify(item, null, 2))}</pre></div></details>`).join("") || `<div class="empty-state">Evidence will appear after a verification run.</div>`;
  const transactions = (state.evidence || []).map((item) => decodePayment(item.txId)?.transaction).filter(Boolean);
  $("txList").innerHTML = transactions.length ? transactions.map((tx) => `<div class="ledger-tx"><span class="tx-check">✓</span><code>${esc(short(tx, 28))}</code><button class="copy-btn" data-copy="${esc(tx)}">COPY</button></div>`).join("") : `<div class="empty-state">Settlement transaction IDs appear after a paid run.</div>`;
  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", () => copyValue(button.dataset.copy, button)));
}

function answer(kind) {
  if (!currentState) return "Run a scenario first so CargoProof AI can explain the live state.";
  const state = currentState;
  if (kind === "payments") return `The agent spent ${money(state.spendUsd)} on independent evidence. It paid only the providers required by the evidence plan: ${state.evidence.map((item) => `${item.provider} (${money(item.priceUsd)})`).join(" and ")}.`;
  if (kind === "decision") return state.escrow === "RELEASED" ? "The verification engine found no failed rules, returned VERIFIED, and authorized RELEASE. The escrow moved to RELEASED." : "The verification engine found a material conflict. It returned a non-release decision, so CargoProof kept the funds HELD.";
  return `The ${state.scenario} scenario for ${state.scenario === "clean" ? "CP001" : "CP002"} completed with ${state.escrow}. Confidence is ${percent(state.confidence)} and ${state.evidence.length} evidence sources were procured.`;
}

function render(state) { currentState = state; renderSummary(state); renderPipeline(state); renderProviders(state); renderTimeline(state); renderRules(state); renderEvidence(state); if (window.CargoProofAssistant) window.CargoProofAssistant.onStateUpdate(state); }

async function run(scenario) {
  selectedScenario = scenario;
  document.querySelectorAll(".scenario-btn").forEach((button) => button.classList.toggle("selected", button.dataset.scenario === scenario));
  $("runButton").disabled = true;
  $("runButton").innerHTML = `<span class="spinner"></span> Running verification...`;
  $("runStatus").textContent = "Agent planning · purchasing evidence · verifying";
  try {
    const response = await fetch(`${API}/api/reset`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ scenario }) });
    if (!response.ok) throw new Error(`CargoProof API returned HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    $("runStatus").textContent = error.message;
    $("timeline").innerHTML = `<div class="error-state"><strong>Verification unavailable</strong><span>${esc(error.message)}</span><small>Check that CargoProof Server is running on port 4021.</small></div>`;
  } finally {
    $("runButton").disabled = false;
    $("runButton").innerHTML = `<span class="run-icon">↗</span> Run Cargo Verification`;
  }
}

async function loadState() { try { const response = await fetch(`${API}/api/state`); if (response.ok) render(await response.json()); } catch { $("runStatus").textContent = "Backend connection unavailable"; } }
async function copyValue(value, button) { try { await navigator.clipboard.writeText(value); const original = button.textContent; button.textContent = "COPIED"; setTimeout(() => { button.textContent = original; }, 1200); } catch { button.textContent = "COPY FAILED"; } }

document.querySelectorAll(".scenario-btn").forEach((button) => button.addEventListener("click", () => { selectedScenario = button.dataset.scenario; document.querySelectorAll(".scenario-btn").forEach((item) => item.classList.toggle("selected", item === button)); run(selectedScenario); }));
$("runButton").addEventListener("click", () => run(selectedScenario));
loadState();
