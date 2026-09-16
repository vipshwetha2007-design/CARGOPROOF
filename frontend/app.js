const API = "";

const $ = (id) => document.getElementById(id);

function money(v) {
  return `$${Number(v || 0).toFixed(2)}`;
}

function pct(v) {
  return `${Math.round(Number(v || 0) * 100)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/*
 * ------------------------------------------------------------
 * x402 PAYMENT LIFECYCLE
 * ------------------------------------------------------------
 */

function getPaymentState(events) {
  const hasPaymentRequired =
    events.some(
      (e) => e.type === "PAYMENT_REQUIRED"
    );

  const hasEvidence =
    events.some(
      (e) => e.type === "EVIDENCE"
    );

  const hasPaymentResponse =
    events.some(
      (e) =>
        e.paymentResponse ||
        e.txId
    );

  return {
    requested: true,
    paymentRequired: hasPaymentRequired,
    paymentConfirmed:
      hasPaymentResponse || hasEvidence,
    evidenceReleased: hasEvidence,
  };
}


/*
 * ------------------------------------------------------------
 * PAYMENT PANEL
 * ------------------------------------------------------------
 */

function renderPaymentPanel(data) {
  const events = data.events || [];
  const payment = getPaymentState(events);

  const evidence =
    data.evidence || [];

  const paidEvidence =
    evidence.filter(
      (e) => e.paid
    );

  const totalPaid =
    paidEvidence.reduce(
      (sum, e) =>
        sum + Number(e.priceUsd || 0),
      0
    );

  const latestPayment =
    paidEvidence.length
      ? paidEvidence[paidEvidence.length - 1]
      : null;

  const txId =
    latestPayment?.txId || "";

  return `
    <div class="payment-panel">

      <div class="payment-header">
        <div>
          <div class="payment-label">
            x402 PAYMENT LIFECYCLE
          </div>

          <div class="payment-title">
            Autonomous Evidence Procurement
          </div>
        </div>

        <div class="payment-status ${
          payment.paymentConfirmed
            ? "success"
            : payment.paymentRequired
              ? "processing"
              : "waiting"
        }">
          ${
            payment.paymentConfirmed
              ? "✓ CONFIRMED"
              : payment.paymentRequired
                ? "⟳ PROCESSING"
                : "WAITING"
          }
        </div>
      </div>


      <div class="payment-steps">

        <div class="payment-step complete">
          <div class="step-icon">🤖</div>

          <div class="step-content">
            <strong>Information requested</strong>

            <span>
              AI agent requested independent
              shipment evidence.
            </span>
          </div>

          <div class="step-state">✓</div>
        </div>


        <div class="payment-step ${
          payment.paymentRequired
            ? "complete"
            : ""
        }">

          <div class="step-icon">💳</div>

          <div class="step-content">
            <strong>
              HTTP 402 — Payment Required
            </strong>

            <span>
              Evidence provider requires payment
              before releasing data.
            </span>
          </div>

          <div class="step-state">
            ${
              payment.paymentRequired
                ? "✓"
                : "○"
            }
          </div>
        </div>


        <div class="payment-step ${
          payment.paymentConfirmed
            ? "complete"
            : payment.paymentRequired
              ? "active"
              : ""
        }">

          <div class="step-icon">💰</div>

          <div class="step-content">
            <strong>
              x402 autonomous payment
            </strong>

            <span>
              Agent creates and signs the
              Algorand USDC payment.
            </span>
          </div>

          <div class="step-state">
            ${
              payment.paymentConfirmed
                ? "✓"
                : payment.paymentRequired
                  ? "⟳"
                  : "○"
            }
          </div>
        </div>


        <div class="payment-step ${
          payment.paymentConfirmed
            ? "complete"
            : ""
        }">

          <div class="step-icon">⛓</div>

          <div class="step-content">
            <strong>
              Algorand settlement
            </strong>

            <span>
              ${
                payment.paymentConfirmed
                  ? `${money(totalPaid)} USDC transferred on TestNet.`
                  : "Waiting for blockchain settlement."
              }
            </span>

            ${
              txId
                ? `
                  <div class="tx-box">
                    <span>Transaction</span>
                    <code>
                      ${escapeHtml(
                        txId.length > 32
                          ? txId.slice(0, 32) + "..."
                          : txId
                      )}
                    </code>
                  </div>
                `
                : ""
            }
          </div>

          <div class="step-state">
            ${
              payment.paymentConfirmed
                ? "✓"
                : "○"
            }
          </div>
        </div>


        <div class="payment-step ${
          payment.evidenceReleased
            ? "complete"
            : ""
        }">

          <div class="step-icon">📡</div>

          <div class="step-content">
            <strong>
              Evidence released
            </strong>

            <span>
              ${
                payment.evidenceReleased
                  ? "Provider released the requested evidence."
                  : "Evidence is locked until payment succeeds."
              }
            </span>
          </div>

          <div class="step-state">
            ${
              payment.evidenceReleased
                ? "✓"
                : "○"
            }
          </div>
        </div>

      </div>


      <div class="payment-summary">

        <div>
          <span>Network</span>
          <strong>Algorand TestNet</strong>
        </div>

        <div>
          <span>Asset</span>
          <strong>USDC · 10458941</strong>
        </div>

        <div>
          <span>Evidence spend</span>
          <strong>${money(totalPaid)}</strong>
        </div>

      </div>

    </div>
  `;
}


/*
 * ------------------------------------------------------------
 * MAIN RENDER
 * ------------------------------------------------------------
 */

function render(data) {

  $("confidence").textContent =
    pct(data.confidence);

  $("confidenceBar").style.width =
    pct(data.confidence);

  $("spend").textContent =
    money(data.spendUsd);


  $("escrow").textContent =
    data.escrow;

  $("escrow").className =
    `escrow ${String(
      data.escrow || ""
    ).toLowerCase()}`;


  $("decision").textContent =
    data.escrow === "HELD"
      ? "BLOCK RELEASE"
      : data.escrow === "RELEASED"
        ? "RELEASE"
        : "VERIFYING";


  $("decision").className =
    `decision ${String(
      data.escrow || ""
    ).toLowerCase()}`;


  $("escrowNext").textContent =
    data.escrow === "HELD"
      ? "HELD"
      : data.escrow === "RELEASED"
        ? "RELEASED"
        : "HELD";


  /*
   * PAYMENT PANEL
   */

  const paymentContainer =
    $("paymentPanel");

  if (paymentContainer) {
    paymentContainer.innerHTML =
      renderPaymentPanel(data);
  }


  /*
   * TIMELINE
   */

  $("timeline").innerHTML =
    (data.events || [])
      .map((e) => {

        const type =
          String(e.type || "");

        let icon = "•";

        if (type === "AGENT")
          icon = "🤖";

        if (type === "PAYMENT_REQUIRED")
          icon = "💳";

        if (type === "EVIDENCE")
          icon = "📡";

        if (type === "DECISION")
          icon = "🧠";

        return `
          <div class="event event-${type.toLowerCase()}">

            <div class="event-type">
              ${icon} ${escapeHtml(type)}
            </div>

            <div class="event-msg">
              ${escapeHtml(e.message)}
            </div>

            <div class="event-time">
              ${new Date(e.time)
                .toLocaleTimeString()}
            </div>

          </div>
        `;
      })
      .join("");


  /*
   * EVIDENCE
   */

  $("evidence").innerHTML =
    (data.evidence || [])
      .map((e, i) => {

        return `
          <div class="evidence-item">

            <div class="evidence-head">

              <span>
                ${i + 1}.
                ${escapeHtml(
                  e.provider ||
                  "Evidence Provider"
                )}
              </span>

              <span>
                ${money(e.priceUsd)}
              </span>

            </div>

            <div class="evidence-meta">
              ${escapeHtml(
                e.observed || ""
              )}
            </div>

            <div class="evidence-meta">

              ${
                e.simulated
                  ? "SIMULATED DOMAIN DATA"
                  : "LIVE"
              }

              ·

              ${
                e.paid
                  ? "x402 PAID"
                  : "UNPAID"
              }

            </div>

            ${
              e.txId
                ? `
                  <div class="tx-inline">
                    Transaction:
                    <code>
                      ${escapeHtml(
                        e.txId
                      )}
                    </code>
                  </div>
                `
                : ""
            }

          </div>
        `;
      })
      .join("");
}


/*
 * ------------------------------------------------------------
 * RUN
 * ------------------------------------------------------------
 */

async function run(scenario) {

  $("timeline").innerHTML = `
    <div class="empty">
      🤖 AI agent is starting shipment verification...
    </div>
  `;


  const paymentPanel =
    $("paymentPanel");

  if (paymentPanel) {

    paymentPanel.innerHTML = `
      <div class="payment-panel">

        <div class="payment-header">

          <div>
            <div class="payment-label">
              x402 PAYMENT LIFECYCLE
            </div>

            <div class="payment-title">
              Requesting evidence...
            </div>
          </div>

          <div class="payment-status processing">
            ⟳ STARTING
          </div>

        </div>

        <div class="payment-step active">

          <div class="step-icon">
            🤖
          </div>

          <div class="step-content">

            <strong>
              Information requested
            </strong>

            <span>
              AI agent is requesting
              shipment evidence.
            </span>

          </div>

          <div class="step-state">
            ⟳
          </div>

        </div>

      </div>
    `;
  }


  try {

    const r =
      await fetch(
        `${API}/api/reset`,
        {
          method: "POST",

          headers: {
            "content-type":
              "application/json"
          },

          body: JSON.stringify({
            scenario
          })
        }
      );


    if (!r.ok) {

      throw new Error(
        `CargoProof API returned HTTP ${r.status}`
      );

    }


    const data =
      await r.json();


    render(data);

  } catch (error) {

    console.error(error);

    $("timeline").innerHTML = `
      <div class="empty">
        ❌ Verification failed:
        ${escapeHtml(error.message)}
      </div>
    `;
  }
}


$("fraudBtn").onclick =
  () => run("fraud");

$("cleanBtn").onclick =
  () => run("clean");