(() => {
  const PIN_KEY = "stage_app_pin";
  let dashboard = null;
  let refreshing = false;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  function getPin() {
    return sessionStorage.getItem(PIN_KEY) || "";
  }

  function setPin(pin) {
    sessionStorage.setItem(PIN_KEY, pin);
  }

  function clearPin() {
    sessionStorage.removeItem(PIN_KEY);
  }

  function showUnlock(msg) {
    const unlock = $("#unlock");
    if (unlock) unlock.classList.remove("hidden");
    if (msg) $("#pin-err").textContent = msg;
  }

  function hideUnlock() {
    $("#unlock").classList.add("hidden");
    $("#pin-err").textContent = "";
  }

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
  }

  function headers(json = false) {
    // FastAPI expects X-App-Pin (alias on Header); do not use Authorization.
    const h = { "X-App-Pin": getPin() };
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      ...opts,
      cache: "no-store",
      headers: { ...headers(!!opts.body), ...(opts.headers || {}) },
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    if (!res.ok) {
      if (res.status === 401) {
        clearPin();
        showUnlock("Session expired — enter PIN again");
      }
      const detail = data && data.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : detail && detail.message
            ? detail.message
            : res.statusText;
      const err = new Error(msg || "request failed");
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function showModal(title, body) {
    $("#modal-title").textContent = title;
    $("#modal-body").textContent = body;
    $("#modal").classList.remove("hidden");
  }

  $("#modal-close").addEventListener("click", () => {
    $("#modal").classList.add("hidden");
  });
  $("#modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") $("#modal").classList.add("hidden");
  });

  function switchTab(name) {
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
  }

  $$(".tab").forEach((t) => {
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });

  function renderTop10(data) {
    const tb = $("#top10-body");
    tb.innerHTML = "";
    (data.top10 || []).forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.rank}</td><td class="ticker">${esc(r.ticker)}</td><td>${esc(r.score)}</td><td>${esc(r.price)}</td><td>${esc(r.vol_ratio)}</td>`;
      tb.appendChild(tr);
    });
    if (data.qcom) {
      $("#qcom-card").style.display = "";
      const q = data.qcom;
      $("#qcom-body").textContent = `${q.ticker} · ${q.stage || ""} · score ${q.score} · price ${q.price} · vol_ratio ${q.vol_ratio} · confirmed ${q.volume_confirmed} · ${q.action || ""}`;
    }
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTickets(data) {
    const root = $("#tickets-list");
    root.innerHTML = "";
    const tickets = data.tickets || [];
    if (!tickets.length) {
      root.innerHTML = `<div class="card"><p class="reason">No tickets for as-of ${esc(data.asof || "—")}.</p></div>`;
      return;
    }
    tickets.forEach((t) => {
      const card = document.createElement("div");
      card.className = "card";
      const sideCls = (t.side || "").toUpperCase() === "SELL" ? "side sell" : "side";
      const approvedTag = t.approved
        ? `<span class="approved-tag">APPROVED</span>`
        : "";
      card.innerHTML = `
        <h3>
          <span>${esc(t.symbol)}</span>
          <span class="${sideCls}">${esc(t.side)}</span>
          ${approvedTag}
        </h3>
        <div class="row"><span>Limit</span><strong>${esc(t.limit_price ?? "—")}</strong></div>
        <div class="row"><span>Size</span><strong>${t.dollar_amount != null ? "$" + esc(t.dollar_amount) : esc(t.qty ?? "—")}</strong></div>
        <div class="row"><span>Score</span><strong>${esc(t.score ?? "—")}</strong></div>
        <div class="row"><span>Kind</span><strong>${esc(t.signal_kind ?? "")}</strong></div>
        <p class="reason">${esc(t.reason || "")}</p>
        <div class="actions">
          <button class="btn btn-approve" data-act="approve" data-id="${esc(t.ticket_id)}" ${t.approved ? "disabled" : ""} type="button">${t.approved ? "Approved" : "Approve"}</button>
          <button class="btn btn-execute" data-act="execute" data-id="${esc(t.ticket_id)}" ${t.approved ? "" : "disabled"} type="button">Execute</button>
        </div>
      `;
      root.appendChild(card);
    });

    root.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const act = btn.dataset.act;
        btn.disabled = true;
        try {
          if (act === "approve") {
            await api("/api/approve", {
              method: "POST",
              body: JSON.stringify({ ticket_id: id }),
            });
            toast("Approved " + id.split("-").slice(0, 2).join("-"));
            await loadDashboard({ quiet: true });
          } else {
            const res = await api("/api/execute", {
              method: "POST",
              body: JSON.stringify({ ticket_id: id }),
            });
            const text = (res.stdout || "") + (res.stderr ? "\n" + res.stderr : "");
            showModal("Manual entry / execute output", text || "(empty)");
          }
        } catch (e) {
          toast(e.message || "Failed");
          btn.disabled = false;
        }
      });
    });
  }

  function renderDip(data) {
    $("#dip-body").textContent = data.dip_scenario_md || "(no dip_scenario.md)";
  }

  function renderStatus(data) {
    const grid = $("#status-grid");
    const cells = [
      ["As-of day", data.asof || "—"],
      ["Tickets", String(data.ticket_count ?? 0)],
      ["Approved", String((data.approved_ticket_ids || []).length)],
      ["dry_run", data.dry_run ? "true" : "false"],
      ["Schwab creds", data.schwab_creds_present ? "present*" : "absent"],
      ["Equity", data.equity_usd != null ? "$" + data.equity_usd : "—"],
      ["File mtime", data.proposed_mtime || "—"],
    ];
    grid.innerHTML = cells
      .map(
        ([label, value]) =>
          `<div class="stat"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`
      )
      .join("");
    const pos = data.open_positions || [];
    $("#positions-body").textContent = pos.length
      ? pos.map((p) => `${p.symbol} qty=${p.qty}`).join(", ")
      : "None (local ledger empty)";
    $("#approved-body").textContent = (data.approved_ticket_ids || []).join("\n") || "—";
  }

  function formatAsOf(data) {
    const day = data.asof || "—";
    const tz = data.timezone || "America/Tijuana";
    const n = data.ticket_count ?? 0;
    const gen = data.generated_at ? ` · gen ${data.generated_at}` : "";
    return `as-of ${day} · ${n} tickets · ${tz}${gen}`;
  }

  function renderAll(data) {
    dashboard = data;
    $("#asof-line").textContent = formatAsOf(data);
    const badge = $("#dry-badge");
    if (data.dry_run) {
      badge.textContent = "dry_run";
      badge.className = "badge dry";
    } else {
      badge.textContent = "LIVE?";
      badge.className = "badge live";
    }
    renderTop10(data);
    renderTickets(data);
    renderDip(data);
    renderStatus(data);
  }

  async function loadDashboard({ quiet = false } = {}) {
    if (refreshing) return dashboard;
    refreshing = true;
    try {
      const data = await api("/api/dashboard");
      renderAll(data);
      await loadBrokerKeys();
      if (!quiet) {
        /* optional toast only on manual refresh */
      }
      return data;
    } finally {
      refreshing = false;
    }
  }

  async function tryUnlock(pin) {
    const cleaned = String(pin || "").trim();
    if (!cleaned) {
      $("#pin-err").textContent = "Enter PIN";
      return;
    }
    setPin(cleaned);
    $("#pin-err").textContent = "";
    try {
      await loadDashboard({ quiet: true });
      hideUnlock();
    } catch (e) {
      // Only clear stored PIN on auth failure — keep it on network/5xx so a flaky
      // refresh does not force re-entry.
      if (e.status === 401) {
        clearPin();
        $("#pin-err").textContent = "Wrong PIN";
      } else {
        $("#pin-err").textContent = e.message || "Unlock failed";
      }
    }
  }

  $("#pin-go").addEventListener("click", () => {
    tryUnlock($("#pin-input").value);
  });
  $("#pin-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") tryUnlock($("#pin-input").value);
  });

  $("#btn-refresh").addEventListener("click", async () => {
    if (!getPin()) {
      showUnlock("Enter PIN to refresh");
      return;
    }
    try {
      await loadDashboard({ quiet: true });
      toast("Refreshed · as-of " + (dashboard && dashboard.asof ? dashboard.asof : "—"));
    } catch (e) {
      if (e.status !== 401) toast(e.message || "Refresh failed");
    }
  });

  // Refresh when returning to the PWA so the daily scan appears without restart.
  function onForeground() {
    if (!getPin()) return;
    if (document.visibilityState && document.visibilityState !== "visible") return;
    loadDashboard({ quiet: true }).catch(() => {});
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") onForeground();
  });
  window.addEventListener("focus", onForeground);
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) onForeground();
  });

  // Light pull-to-refresh: pull down near top of page.
  let touchStartY = 0;
  let pulling = false;
  document.addEventListener(
    "touchstart",
    (e) => {
      if (window.scrollY <= 0 && e.touches[0]) {
        touchStartY = e.touches[0].clientY;
        pulling = true;
      } else {
        pulling = false;
      }
    },
    { passive: true }
  );
  document.addEventListener(
    "touchend",
    (e) => {
      if (!pulling || !getPin()) return;
      const y = (e.changedTouches[0] && e.changedTouches[0].clientY) || 0;
      if (y - touchStartY > 70) {
        loadDashboard({ quiet: true })
          .then(() => toast("Refreshed · as-of " + (dashboard && dashboard.asof ? dashboard.asof : "—")))
          .catch(() => {});
      }
      pulling = false;
    },
    { passive: true }
  );


  function applyBrokerStatus(st, clearSecrets) {
    const chip = $("#bk-status");
    const connected = !!(st && st.key_saved && st.secret_saved);
    chip.textContent = connected ? "connected" : "no keys saved, trading not wired";
    chip.className = connected ? "chip ok" : "chip warn";
    const card = document.querySelector(".broker-card");
    const editing = card && card.contains(document.activeElement);
    if (!editing) {
      if (st && st.adapter) $("#bk-adapter").value = st.adapter;
      if (st && (st.mode === "paper" || st.mode === "live")) $("#bk-mode").value = st.mode;
    }
    const mask = $("#bk-mask");
    if (st && st.key_saved && st.key_last4) {
      mask.textContent = "API key on file ····" + st.key_last4 + (st.secret_saved ? " · secret saved" : " · secret missing");
    } else if (st && st.key_saved) {
      mask.textContent = "API key on file" + (st.secret_saved ? " · secret saved" : " · secret missing");
    } else if (st && st.secret_saved) {
      mask.textContent = "Secret on file · API key missing";
    } else {
      mask.textContent = "";
    }
    if (clearSecrets) {
      $("#bk-key").value = "";
      $("#bk-secret").value = "";
    }
  }

  async function loadBrokerKeys() {
    const st = await api("/api/broker-keys");
    applyBrokerStatus(st, false);
    return st;
  }


  $("#bk-save").addEventListener("click", async () => {
    const btn = $("#bk-save");
    btn.disabled = true;
    try {
      const st = await api("/api/broker-keys", {
        method: "POST",
        body: JSON.stringify({
          adapter: $("#bk-adapter").value,
          mode: $("#bk-mode").value,
          api_key: $("#bk-key").value,
          api_secret: $("#bk-secret").value,
        }),
      });
      applyBrokerStatus(st, true);
      toast("Keys saved · trading still off");
    } catch (e) {
      if (e.status !== 401) toast(e.message || "Save failed");
    } finally {
      btn.disabled = false;
    }
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  // Auto-unlock if session already has PIN
  if (getPin()) {
    tryUnlock(getPin());
  }
})();
