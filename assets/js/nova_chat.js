(function () {
  "use strict";
  const popup = document.getElementById("nova-chat");
  const trigger = document.querySelector("[data-nova-status]");
  if (!popup || !trigger) return;
  const connection = popup.querySelector("[data-nova-chat-connection]");
  const feedback = popup.querySelector("[data-nova-chat-feedback]");
  const log = popup.querySelector("[data-nova-chat-messages]");
  const form = popup.querySelector("form");
  const input = form.elements.message;
  const send = form.querySelector('[type="submit"]');
  let csrf = "";
  let connected = false;
  let busy = false;
  let inFlight = false;
  let timer;
  let lastView;
  let retry;

  function updateButton() {
    send.disabled = !connected || !csrf || busy || inFlight;
  }

  function append(label, text) {
    const row = document.createElement("p");
    const name = document.createElement("strong");
    name.textContent = label + " ";
    row.append(name, text);
    log.append(row);
  }

  function render(data) {
    csrf = data.csrf;
    connected = data.connected;
    busy = data.messages.some(item => item.state === "queued" || item.state === "running");
    connection.textContent = connected ? "Verbunden" : "Nicht erreichbar";
    if (retry && data.messages.some(item => item.id === retry.id)) retry = null;
    const view = JSON.stringify(data.messages);
    if (view !== lastView) {
      lastView = view;
      log.replaceChildren();
      for (const item of data.messages) {
        append("Du", item.text);
        if (item.reply) append(item.state === "done" ? "NOVA" : "Hinweis", item.reply);
        else append("NOVA", item.state === "running" ? "Antwort wird erstellt …" : "Nachricht wartet …");
      }
      log.scrollTop = log.scrollHeight;
    }
  }

  async function request(message) {
    if (inFlight) return;
    clearTimeout(timer);
    inFlight = true;
    updateButton();
    try {
      const response = await fetch("api/nova_chat.php", {
        cache: "no-store",
        credentials: "same-origin",
        redirect: "error",
        method: message ? "POST" : "GET",
        headers: message ? {"Content-Type": "application/json"} : {},
        body: message ? JSON.stringify({...message, csrf}) : undefined,
        signal: AbortSignal.timeout(5000)
      });
      const data = await response.json().catch(() => null);
      if (data?.contract_version === "mosa2_nova_chat_v1" && Array.isArray(data.messages)) render(data);
      if (!response.ok) {
        const errors = {
          401: "Bitte melde dich erneut auf der Testseite an.",
          403: "Die Sitzung ist abgelaufen. Lade die Seite neu.",
          409: "Eine Anfrage wird bereits bearbeitet.",
          413: "Die Nachricht ist zu lang.",
          422: "Bitte sende gültigen Text mit höchstens 12 KB.",
          503: "Die Verbindung zu NOVA ist derzeit nicht verfügbar.",
          507: "Der Chat-Speicher ist derzeit voll. Versuche es später erneut."
        };
        feedback.textContent = errors[response.status] || "Die Anfrage konnte nicht verarbeitet werden.";
        if (response.status === 503 || response.status === 401 || response.status === 403) connected = false;
      } else if (message && input.value.trim() === message.text) {
        input.value = "";
      }
      if (!connected) connection.textContent = "Nicht erreichbar";
    } catch {
      connected = false;
      connection.textContent = "Nicht erreichbar";
      feedback.textContent = message
        ? "Die Verbindung wurde unterbrochen. Der Chat prüft, ob die Nachricht angekommen ist."
        : "Der Chat konnte nicht geladen werden.";
    } finally {
      inFlight = false;
      updateButton();
      if (popup.open) timer = setTimeout(() => request(), 2000);
    }
  }

  function close() { popup.close(); }
  trigger.addEventListener("click", () => {
    if (popup.open) return close();
    popup.show();
    trigger.setAttribute("aria-expanded", "true");
    feedback.textContent = "";
    input.focus();
    request();
  });
  popup.querySelector("[data-nova-chat-close]").addEventListener("click", close);
  popup.addEventListener("keydown", event => {
    if (event.key === "Escape") close();
    if (event.target === input && event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!send.disabled) form.requestSubmit();
    }
  });
  popup.addEventListener("close", () => {
    clearTimeout(timer);
    trigger.setAttribute("aria-expanded", "false");
    trigger.focus();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    const text = input.value.trim();
    if (send.disabled || !text) return;
    if (new TextEncoder().encode(text).length > 12000) {
      feedback.textContent = "Die Nachricht ist zu lang (maximal 12 KB).";
      return;
    }
    feedback.textContent = "";
    if (retry?.text !== text) retry = {text, id: crypto.randomUUID().replaceAll("-", "")};
    request(retry);
  });
}());
