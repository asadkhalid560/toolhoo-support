/*
 * Embeddable support chat widget.
 *
 *   <script src="https://your-host/widget.js" defer
 *           data-api="https://your-host"
 *           data-accent="#c2410c"
 *           data-title="Product Support"></script>
 *
 * No dependencies. Injects its own styles into a shadow root so nothing on the
 * host page can leak in and break the layout, and nothing here leaks out.
 */
(function () {
  "use strict";

  var script = document.currentScript ||
    document.querySelector('script[src*="widget.js"]');
  var cfg = {
    api: (script && script.dataset.api) ||
      (script && new URL(script.src).origin) || "",
    accent: (script && script.dataset.accent) || "#c2410c",
    title: (script && script.dataset.title) || "Product Support",
    subtitle: (script && script.dataset.subtitle) || "Ask about specs, stock or pricing",
    greeting: (script && script.dataset.greeting) ||
      "Hi! Ask me about any product — specifications, price, stock or delivery.",
  };
  var SUGGESTIONS = (script && script.dataset.suggestions
    ? script.dataset.suggestions.split("|")
    : [
        "What is the price of the 2.5 mm twist drill?",
        "What point angle do the GOLD-P drills have?",
        "Which materials can these drills cut?",
      ]);

  var STORE_KEY = "support_widget_history";
  var history = [];
  try {
    history = JSON.parse(sessionStorage.getItem(STORE_KEY) || "[]");
  } catch (e) { history = []; }

  /* ---------------------------------------------------------------- styles */
  var CSS = `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }
.root {
  --accent: ${cfg.accent};
  --bg: #ffffff;
  --panel: #ffffff;
  --text: #1c1917;
  --muted: #78716c;
  --line: #e7e5e4;
  --bot-bubble: #f5f5f4;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.5;
  color: var(--text);
}
@media (prefers-color-scheme: dark) {
  .root {
    --bg: #1c1917; --panel: #232020; --text: #f5f5f4; --muted: #a8a29e;
    --line: #3a3533; --bot-bubble: #2c2827;
  }
}

/* launcher */
.launcher {
  position: fixed; right: 20px; bottom: 20px; z-index: 2147483000;
  width: 56px; height: 56px; border-radius: 50%; border: 0;
  background: var(--accent); color: #fff; cursor: pointer;
  display: grid; place-items: center;
  box-shadow: 0 6px 20px rgba(0,0,0,.22);
  transition: transform .18s ease, box-shadow .18s ease;
}
.launcher:hover { transform: translateY(-2px) scale(1.04); box-shadow: 0 10px 26px rgba(0,0,0,.28); }
.launcher:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
.launcher svg { width: 26px; height: 26px; }
.launcher .close-icon { display: none; }
.root.open .launcher .chat-icon { display: none; }
.root.open .launcher .close-icon { display: block; }

/* panel */
.panel {
  position: fixed; right: 20px; bottom: 88px; z-index: 2147483000;
  width: 384px; max-width: calc(100vw - 40px);
  height: 580px; max-height: calc(100vh - 120px);
  background: var(--panel); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: 0 24px 60px rgba(0,0,0,.24);
  display: flex; flex-direction: column; overflow: hidden;
  opacity: 0; transform: translateY(12px) scale(.98); pointer-events: none;
  transition: opacity .18s ease, transform .18s ease;
}
.root.open .panel { opacity: 1; transform: none; pointer-events: auto; }

.header { padding: 16px 18px; background: var(--accent); color: #fff; flex: none; }
.header h2 { margin: 0; font-size: 16px; font-weight: 650; letter-spacing: -.01em; }
.header p { margin: 2px 0 0; font-size: 12.5px; opacity: .85; }

.log { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.log::-webkit-scrollbar { width: 8px; }
.log::-webkit-scrollbar-thumb { background: var(--line); border-radius: 4px; }

.msg { max-width: 86%; padding: 10px 13px; border-radius: 14px; word-wrap: break-word; }
.msg.user { align-self: flex-end; background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
.msg.bot { align-self: flex-start; background: var(--bot-bubble); border-bottom-left-radius: 4px; }
.msg.error { align-self: stretch; background: #fee2e2; color: #991b1b; font-size: 13.5px; }
.msg p { margin: 0 0 8px; } .msg p:last-child { margin-bottom: 0; }
.msg ul { margin: 6px 0; padding-left: 20px; } .msg li { margin: 3px 0; }
.msg code { background: rgba(0,0,0,.08); padding: 1px 5px; border-radius: 4px; font-size: 13px; }
.msg strong { font-weight: 650; }

.sources { margin-top: 8px; font-size: 12px; }
.sources summary { cursor: pointer; color: var(--muted); user-select: none; }
.sources ol { margin: 6px 0 0; padding-left: 18px; color: var(--muted); }
.sources li { margin: 4px 0; }

.dots { display: inline-flex; gap: 4px; align-items: center; height: 18px; }
.dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); animation: b 1.2s infinite; }
.dots i:nth-child(2) { animation-delay: .15s; } .dots i:nth-child(3) { animation-delay: .3s; }
@keyframes b { 0%,60%,100% { opacity:.25; transform: translateY(0);} 30% { opacity:1; transform: translateY(-3px);} }

.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font: inherit; font-size: 12.5px; padding: 7px 11px; cursor: pointer;
  border: 1px solid var(--line); background: transparent; color: var(--text);
  border-radius: 999px; text-align: left;
}
.chip:hover { border-color: var(--accent); color: var(--accent); }

.composer { flex: none; border-top: 1px solid var(--line); padding: 10px; display: flex; gap: 8px; align-items: flex-end; }
.composer textarea {
  flex: 1; resize: none; font: inherit; color: var(--text); background: transparent;
  border: 1px solid var(--line); border-radius: 10px; padding: 9px 11px;
  max-height: 96px; min-height: 40px;
}
.composer textarea:focus { outline: none; border-color: var(--accent); }
.send {
  flex: none; width: 40px; height: 40px; border: 0; border-radius: 10px; cursor: pointer;
  background: var(--accent); color: #fff; display: grid; place-items: center;
}
.send:disabled { opacity: .45; cursor: not-allowed; }
.send svg { width: 18px; height: 18px; }
.footer { padding: 0 12px 10px; font-size: 11px; color: var(--muted); text-align: center; }

@media (max-width: 480px) {
  .panel { right: 0; bottom: 0; width: 100vw; max-width: 100vw; height: 100dvh; max-height: 100dvh; border-radius: 0; border: 0; }
  .launcher { right: 16px; bottom: 16px; }
  .root.open .launcher { display: none; }
}`;

  /* ------------------------------------------------------------ rendering */
  function esc(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Model output is markdown. Escape first, then allow a small, fixed subset —
  // never inject raw model text as HTML.
  function md(text) {
    var safe = esc(text);
    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");
    safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    var lines = safe.split("\n"), out = [], list = null;
    lines.forEach(function (line) {
      var m = line.match(/^\s*[-*•]\s+(.*)$/);
      if (m) {
        if (!list) { list = []; }
        list.push("<li>" + m[1] + "</li>");
      } else {
        if (list) { out.push("<ul>" + list.join("") + "</ul>"); list = null; }
        if (line.trim()) { out.push("<p>" + line + "</p>"); }
      }
    });
    if (list) { out.push("<ul>" + list.join("") + "</ul>"); }
    return out.join("");
  }

  /* ------------------------------------------------------------------ DOM */
  var host = document.createElement("div");
  host.setAttribute("data-support-widget", "");
  var shadow = host.attachShadow({ mode: "open" });
  var style = document.createElement("style");
  style.textContent = CSS;
  shadow.appendChild(style);

  var root = document.createElement("div");
  root.className = "root";
  root.innerHTML = `
<div class="panel" role="dialog" aria-modal="false" aria-label="${esc(cfg.title)}">
  <div class="header">
    <h2>${esc(cfg.title)}</h2>
    <p>${esc(cfg.subtitle)}</p>
  </div>
  <div class="log" id="log" aria-live="polite"></div>
  <div class="composer">
    <textarea id="input" rows="1" placeholder="Ask a question…" aria-label="Your question"></textarea>
    <button class="send" id="send" aria-label="Send">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
    </button>
  </div>
  <div class="footer">Answers come from our product documentation.</div>
</div>
<button class="launcher" id="launcher" aria-label="Open support chat" aria-expanded="false">
  <svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.1A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z"/></svg>
  <svg class="close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
</button>`;
  shadow.appendChild(root);
  document.body.appendChild(host);

  var log = shadow.getElementById("log");
  var input = shadow.getElementById("input");
  var sendBtn = shadow.getElementById("send");
  var launcher = shadow.getElementById("launcher");
  var busy = false;

  function scroll() { log.scrollTop = log.scrollHeight; }

  function addMessage(role, html) {
    var el = document.createElement("div");
    el.className = "msg " + role;
    el.innerHTML = html;
    log.appendChild(el);
    scroll();
    return el;
  }

  function addSources(el, items) {
    if (!items || !items.length) { return; }
    var d = document.createElement("details");
    d.className = "sources";
    d.innerHTML = "<summary>Sources (" + items.length + ")</summary><ol>" +
      items.map(function (s) {
        return "<li>" + esc(s.source) + " — " + Math.round(s.score * 100) + "% match</li>";
      }).join("") + "</ol>";
    el.appendChild(d);
    scroll();
  }

  function showSuggestions() {
    var wrap = document.createElement("div");
    wrap.className = "msg bot";
    wrap.innerHTML = md(cfg.greeting);
    var chips = document.createElement("div");
    chips.className = "chips";
    chips.style.marginTop = "10px";
    SUGGESTIONS.forEach(function (q) {
      var b = document.createElement("button");
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", function () { send(q); });
      chips.appendChild(b);
    });
    wrap.appendChild(chips);
    log.appendChild(wrap);
    scroll();
  }

  function restore() {
    if (!history.length) { showSuggestions(); return; }
    history.forEach(function (m) {
      addMessage(m.role === "user" ? "user" : "bot", md(m.content));
    });
  }

  function persist() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(history.slice(-20))); }
    catch (e) { /* private mode — history stays in memory only */ }
  }

  /* -------------------------------------------------------------- network */
  function send(text) {
    text = (text || input.value).trim();
    if (!text || busy) { return; }
    busy = true;
    sendBtn.disabled = true;
    input.value = "";
    input.style.height = "auto";

    addMessage("user", md(text));

    var bubble = addMessage("bot", '<div class="dots"><i></i><i></i><i></i></div>');
    var answer = "";
    var sources = null;
    var priorHistory = history.slice();
    history.push({ role: "user", content: text });

    fetch(cfg.api + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: priorHistory }),
    })
      .then(function (res) {
        if (!res.ok || !res.body) { throw new Error("HTTP " + res.status); }
        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function pump() {
          return reader.read().then(function (r) {
            if (r.done) { return finish(); }
            buffer += decoder.decode(r.value, { stream: true });
            var parts = buffer.split("\n\n");
            buffer = parts.pop();
            parts.forEach(function (chunk) {
              var line = chunk.replace(/^data:\s*/, "");
              if (!line) { return; }
              var ev;
              try { ev = JSON.parse(line); } catch (e) { return; }
              if (ev.type === "sources") {
                sources = ev.items;
              } else if (ev.type === "delta") {
                answer += ev.text;
                bubble.innerHTML = md(answer);
                scroll();
              } else if (ev.type === "error") {
                bubble.className = "msg error";
                bubble.textContent = "Sorry — " + ev.message;
              }
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        bubble.className = "msg error";
        bubble.textContent = "Could not reach support: " + err.message;
      })
      .then(finish);

    function finish() {
      if (answer) {
        bubble.innerHTML = md(answer);
        addSources(bubble, sources);
        history.push({ role: "assistant", content: answer });
        persist();
      }
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  /* --------------------------------------------------------------- events */
  function toggle(open) {
    var isOpen = open === undefined ? !root.classList.contains("open") : open;
    root.classList.toggle("open", isOpen);
    launcher.setAttribute("aria-expanded", String(isOpen));
    launcher.setAttribute("aria-label", isOpen ? "Close support chat" : "Open support chat");
    if (isOpen) { setTimeout(function () { input.focus(); }, 180); }
  }

  launcher.addEventListener("click", function () { toggle(); });
  sendBtn.addEventListener("click", function () { send(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 96) + "px";
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && root.classList.contains("open")) { toggle(false); }
  });

  restore();
})();
