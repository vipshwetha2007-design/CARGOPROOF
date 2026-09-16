(function () {
  "use strict";

  const API = "http://localhost:4021";

  const $ = (id) => document.getElementById(id);
  const esc = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const messagesEl = $("chatMessages");
  const formEl = $("chatForm");
  const inputEl = $("chatInput");
  const sendBtn = $("chatSend");
  const badgeEl = $("assistantBadge");
  const suggestionsEl = $("chatSuggestions");

  if (!messagesEl || !formEl || !inputEl) return;

  const LORA_LABEL = "View on Lora";

  function shortenId(value, length = 14) {
    if (!value) return "";
    return value.length > length ? `${value.slice(0, length)}...` : value;
  }

  /** Turn plain-text assistant replies + any tx/lora_url into safe HTML. */
  function renderAssistantBody(payload) {
    const lines = String(payload.message || "").split("\n");
    let html = lines
      .map((line) => (line.trim() ? `<p>${esc(line)}</p>` : ""))
      .join("");

    if (payload.lora_url) {
      html += `<a class="lora-link" href="${esc(payload.lora_url)}" target="_blank" rel="noopener">${LORA_LABEL} ↗</a>`;
    }

    if (payload.transaction && payload.transaction.id) {
      const t = payload.transaction;
      html += `<div class="tx-card">
        <div class="tx-card-row"><span>Status</span><b>${esc(t.status || "UNKNOWN")}</b></div>
        <div class="tx-card-row"><span>Network</span><b>Algorand Testnet</b></div>
        ${t.confirmedRound ? `<div class="tx-card-row"><span>Round</span><b>${esc(t.confirmedRound)}</b></div>` : ""}
        ${t.sender ? `<div class="tx-card-row"><span>Sender</span><b>${esc(shortenId(t.sender, 18))}</b></div>` : ""}
        ${t.assetTransfer ? `<div class="tx-card-row"><span>Amount</span><b>${esc(t.assetTransfer.amount)} (asset ${esc(t.assetTransfer.assetId)})</b></div>` : ""}
        <div class="tx-card-row"><span>Transaction</span><code title="${esc(t.id)}">${esc(shortenId(t.id, 20))}</code>
          <button type="button" class="copy-btn" data-copy="${esc(t.id)}">COPY</button>
        </div>
      </div>`;
    }

    if (Array.isArray(payload.transactions) && payload.transactions.length) {
      html += payload.transactions
        .map(
          (tx) =>
            `<div class="tx-card"><div class="tx-card-row"><span>Payment TX</span><code title="${esc(tx.id)}">${esc(shortenId(tx.id, 20))}</code>
              <button type="button" class="copy-btn" data-copy="${esc(tx.id)}">COPY</button></div>
              ${tx.lora_url ? `<a class="lora-link" href="${esc(tx.lora_url)}" target="_blank" rel="noopener">${LORA_LABEL} ↗</a>` : ""}
            </div>`
        )
        .join("");
    }

    return html;
  }

  function appendMessage(role, htmlOrText, isHtml) {
    const row = document.createElement("div");
    row.className = `chat-msg chat-msg-${role}`;
    if (isHtml) {
      row.innerHTML = htmlOrText;
    } else {
      const p = document.createElement("p");
      p.textContent = htmlOrText;
      row.appendChild(p);
    }
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
  }

  function appendTyping() {
    const row = document.createElement("div");
    row.className = "chat-msg chat-msg-assistant chat-msg-typing";
    row.innerHTML = `<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>`;
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
  }

  function wireCopyButtons(scope) {
    scope.querySelectorAll("[data-copy]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(button.dataset.copy);
          const original = button.textContent;
          button.textContent = "COPIED";
          setTimeout(() => {
            button.textContent = original;
          }, 1200);
        } catch {
          button.textContent = "COPY FAILED";
        }
      });
    });
  }

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed) return;

    appendMessage("user", trimmed, false);
    inputEl.value = "";
    inputEl.disabled = true;
    sendBtn.disabled = true;
    if (badgeEl) {
      badgeEl.textContent = "THINKING";
      badgeEl.className = "local-badge processing";
    }

    const typingRow = appendTyping();

    try {
      const response = await fetch(`${API}/api/v1/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      const payload = await response.json().catch(() => null);

      typingRow.remove();

      if (!response.ok || !payload) {
        appendMessage(
          "assistant",
          `<p>The CargoProof Assistant couldn't reach the backend (HTTP ${response.status}). Make sure the CargoProof server is running.</p>`,
          true
        );
      } else {
        const row = appendMessage("assistant", renderAssistantBody(payload), true);
        wireCopyButtons(row);

        // Reflect a completed verification back into the main dashboard state
        // so the two views stay in sync — reuses the dashboard's own render().
        if (
          payload.intent === "VERIFY_SHIPMENT" &&
          typeof window.loadState === "function"
        ) {
          window.loadState();
        }
      }
    } catch (error) {
      typingRow.remove();
      appendMessage(
        "assistant",
        `<p>Connection error talking to the CargoProof backend: ${esc(error.message)}</p>`,
        true
      );
    } finally {
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.focus();
      if (badgeEl) {
        badgeEl.textContent = "LIVE BACKEND";
        badgeEl.className = "local-badge";
      }
    }
  }

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(inputEl.value);
  });

  if (suggestionsEl) {
    suggestionsEl.querySelectorAll("[data-prompt]").forEach((button) => {
      button.addEventListener("click", () => sendMessage(button.dataset.prompt));
    });
  }

  // Exposed so dashboard.js can notify us of state changes if useful later.
  window.CargoProofAssistant = {
    onStateUpdate() {
      // Intentionally minimal: the assistant reads live state on demand via
      // its own backend calls rather than mirroring dashboard state here.
    },
  };
})();
