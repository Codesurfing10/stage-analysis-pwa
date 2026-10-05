(() => {
  const PIN_KEY = "stage_app_pin";

  const $ = (sel) => document.querySelector(sel);

  function getPin() {
    return sessionStorage.getItem(PIN_KEY) || "";
  }
  function setPin(pin) {
    sessionStorage.setItem(PIN_KEY, pin);
  }

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2600);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function clearPin() {
    sessionStorage.removeItem(PIN_KEY);
  }

  function showUnlock(msg) {
    $("#app").classList.add("hidden");
    $("#unlock").classList.remove("hidden");
    if (msg) $("#pin-err").textContent = msg;
  }

  function headers(json = false) {
    // FastAPI Header alias X-App-Pin
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

  function fmtNum(v, digits = 2) {
    if (v == null || v === "") return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return esc(v);
    return n.toFixed(digits);
  }

  function fmtPct(v) {
    if (v == null || v === "") return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return esc(v);
    const pct = Math.abs(n) < 1 && Math.abs(n) > 0 ? n * 100 : n;
    return (pct >= 0 ? "+" : "") + pct.toFixed(1) + "%";
  }

  function stageClass(stage) {
    const s = String(stage || "").toLowerCase();
    if (s.includes("stage 2")) return "s2";
    if (s.includes("stage 1")) return "s1";
    if (s.includes("stage 3")) return "s3";
    if (s.includes("stage 4")) return "s4";
    return "";
  }

  function scoreBar(score, maxScore) {
    const n = Number(score);
    if (Number.isNaN(n)) return `<span class="score-num">${esc(score)}</span>`;
    const pct = Math.max(0, Math.min(100, (n / maxScore) * 100));
    return `<div class="score-cell"><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><span class="score-num">${fmtNum(n, 1)}</span></div>`;
  }

  function renderTop10(data) {
    const rows = data.top10 || [];
    $("#top10-sub").textContent = rows.length
      ? `${rows.length} names · from market_top10 / scan`
      : "No top-10 data";
    const scores = rows.map((r) => Number(r.score)).filter((n) => !Number.isNaN(n));
    const maxScore = scores.length ? Math.max(...scores, 100) : 120;
    const tb = $("#top10-body");
    tb.innerHTML = rows
      .map((r) => {
        const conf = String(r.volume_confirmed || "").toUpperCase();
        const confY = conf === "Y" || conf === "TRUE" || conf === "1";
        return `<tr>
          <td>${esc(r.rank)}</td>
          <td class="ticker">${esc(r.ticker)}</td>
          <td class="name">${esc(r.name)}</td>
          <td>${scoreBar(r.score, maxScore)}</td>
          <td></td>
          <td>${esc(r.price)}</td>
          <td>${esc(r.vol_ratio)}</td>
          <td style="color:${confY ? "var(--green)" : "var(--muted)"}">${confY ? "Y" : esc(r.volume_confirmed || "—")}</td>
          <td>${esc(r.extended_pct)}</td>
        </tr>`;
      })
      .join("");
  }

  function renderTickets(data) {
    const tickets = data.tickets || [];
    $("#tickets-sub").textContent = `${tickets.length} proposed · ${
      (data.approved_ticket_ids || []).length
    } approved`;
    $("#ticket-badge").textContent = `${tickets.length} tickets`;
    const empty = $("#tickets-empty");
    const tb = $("#tickets-body");
    if (!tickets.length) {
      tb.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    tb.innerHTML = tickets
      .map((t) => {
        const side = String(t.side || "").toUpperCase();
        const sideCls = side === "SELL" ? "side-sell" : "side-buy";
        const size =
          t.dollar_amount != null
            ? "$" + Number(t.dollar_amount).toLocaleString()
            : t.qty != null
              ? String(t.qty)
              : "—";
        const status = t.approved
          ? `<span class="tag approved">Approved</span>`
          : `<span class="tag proposed">Proposed</span>`;
        const btn = t.approved
          ? `<button class="btn btn-sm btn-approve" disabled type="button">Done</button>`
          : `<button class="btn btn-sm btn-approve" data-act="approve" data-id="${esc(
              t.ticket_id
            )}" type="button">Approve</button>`;
        return `<tr title="${esc(t.reason || "")}">
          <td class="ticker">${esc(t.symbol)}</td>
          <td class="${sideCls}">${esc(side)}</td>
          <td>${fmtNum(t.limit_price, 2)}</td>
          <td>${esc(size)}</td>
          <td>${fmtNum(t.score, 1)}</td>
          <td>${status}</td>
          <td>${btn}</td>
        </tr>`;
      })
      .join("");

    tb.querySelectorAll("button[data-act=approve]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        btn.disabled = true;
        try {
          await api("/api/approve", {
            method: "POST",
            body: JSON.stringify({ ticket_id: id }),
          });
          toast("Approved " + id);
          await loadAll();
        } catch (e) {
          toast(e.message || "Approve failed");
          btn.disabled = false;
        }
      });
    });
  }

  function renderPositions(ps) {
    const rows = (ps && ps.positions) || [];
    $("#pos-sub").textContent = rows.length
      ? `${rows.length} positions · as-of ${ps.asof || "—"}`
      : "No positions_stage artifact";
    const empty = $("#pos-empty");
    const tb = $("#pos-body");
    if (!rows.length) {
      tb.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    tb.innerHTML = rows
      .map((p) => {
        const sc = stageClass(p.stage);
        const shortStage = String(p.stage || "")
          .replace(/\(.*?\)/g, "")
          .trim();
        return `<tr>
          <td class="ticker">${esc(p.symbol)}</td>
          <td><span class="stage-pill ${sc}">${esc(shortStage || p.stage)}</span></td>
          <td>${fmtNum(p.price, 2)}</td>
          <td>${fmtNum(p.sma50, 2)}</td>
          <td>${fmtNum(p.sma150, 2)}</td>
          <td>${fmtNum(p.sma150_slope, 4)}</td>
          <td>${fmtNum(p.vol_ratio, 2)}</td>
          <td>${fmtPct(p.extended_pct)}</td>
        </tr>`;
      })
      .join("");
  }

  function renderBeta(beta) {
    const empty = $("#beta-empty");
    const summary = $("#beta-summary");
    const bars = $("#beta-bars");
    if (!beta || !beta.available) {
      $("#beta-sub").textContent = "No beta artifact";
      summary.innerHTML = "";
      bars.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    $("#beta-sub").textContent = `as-of ${beta.asof || "—"} · ${
      beta.generated_at_pt || ""
    }`.trim();

    const port = beta.portfolio_spy_1y || {};
    const cards = [
      { label: "Portfolio β (SPY 1y)", value: fmtNum(port.beta, 3), hint: `R² ${fmtNum(port.r2, 3)}` },
      { label: "Corr vs SPY", value: fmtNum(port.corr, 3), hint: port.window || "1y" },
      {
        label: "Ann. vol",
        value: port.ann_vol != null ? (Number(port.ann_vol) * 100).toFixed(1) + "%" : "—",
        hint: "equal-weight",
      },
      {
        label: "Symbols",
        value: String((beta.symbols || []).length),
        hint: "positions",
      },
    ];
    summary.innerHTML = cards
      .map(
        (c) =>
          `<div class="stat-card"><div class="label">${esc(c.label)}</div><div class="value">${esc(
            c.value
          )}</div><div class="hint">${esc(c.hint)}</div></div>`
      )
      .join("");

    const list =
      beta.per_symbol_spy_1y ||
      beta.spy_1y_sorted_by_abs_beta ||
      [];
    const maxAbs = Math.max(
      0.01,
      ...list.map((r) => Math.abs(Number(r.beta) || 0))
    );
    bars.innerHTML = list
      .map((r) => {
        const b = Number(r.beta) || 0;
        const pct = Math.min(100, (Math.abs(b) / maxAbs) * 100);
        return `<div class="beta-row">
          <div class="sym">${esc(r.symbol)}</div>
          <div class="beta-track"><div class="beta-fill" style="width:${pct}%"></div></div>
          <div class="num">${fmtNum(b, 2)}</div>
          <div class="corr">${fmtNum(r.corr, 2)}</div>
        </div>`;
      })
      .join("");
  }

  function renderQcom(q) {
    const body = $("#qcom-body");
    const empty = $("#qcom-empty");
    if (!q) {
      body.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    const fields = [
      ["Ticker", q.ticker],
      ["Stage", q.stage],
      ["Action", q.action],
      ["Price", q.price],
      ["Score", q.score],
      ["SMA150", q.sma150],
      ["SMA50", q.sma50],
      ["Slope", q.slope],
      ["Vol ratio", q.vol_ratio],
      ["Vol conf", q.volume_confirmed],
      ["Extended %", q.extended_pct],
      ["As-of", q.asof],
    ];
    body.innerHTML = fields
      .map(
        ([k, v]) =>
          `<div class="kv"><div class="k">${esc(k)}</div><div class="v">${esc(
            v ?? "—"
          )}</div></div>`
      )
      .join("");
  }

  function renderDip(md) {
    $("#dip-body").textContent = md || "(no dip_scenario.md)";
  }

  function renderHeader(data) {
    const n = data.ticket_count ?? 0;
    $("#asof-line").textContent = `as-of ${data.asof || "—"} · ${n} tickets · ${
      data.timezone || "America/Tijuana"
    } · equity ${
      data.equity_usd != null ? "$" + Number(data.equity_usd).toLocaleString() : "—"
    }${data.proposed_mtime ? " · file " + data.proposed_mtime : ""}`;
    const badge = $("#dry-badge");
    if (data.dry_run !== false) {
      badge.textContent = "dry_run";
      badge.className = "badge dry";
    } else {
      badge.textContent = "LIVE?";
      badge.className = "badge live";
    }
  }


  function applyBrokerStatus(st, clearSecrets) {
    const chip = $("#bk-status");
    const connected = !!(st && st.key_saved && st.secret_saved);
    chip.textContent = connected ? "connected" : "no keys saved, trading not wired";
    chip.className = connected ? "badge bk-chip ok" : "badge bk-chip warn";
    const card = $("#sec-broker");
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

  async function loadAll() {
    const data = await api("/api/dashboard");
    renderHeader(data);
    renderTop10(data);
    renderTickets(data);
    renderPositions(data.positions_stage);
    renderBeta(data.positions_beta);
    renderQcom(data.qcom);
    renderDip(data.dip_scenario_md);
    await loadBrokerKeys();
    return data;
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
      await loadAll();
      $("#unlock").classList.add("hidden");
      $("#app").classList.remove("hidden");
    } catch (e) {
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
      const data = await loadAll();
      toast("Refreshed · as-of " + (data.asof || "—"));
    } catch (e) {
      if (e.status !== 401) toast(e.message || "Refresh failed");
    }
  });

  function onForeground() {
    if (!getPin()) return;
    if (document.visibilityState && document.visibilityState !== "visible") return;
    loadAll().catch(() => {});
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") onForeground();
  });
  window.addEventListener("focus", onForeground);
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) onForeground();
  });


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

  if (getPin()) {
    tryUnlock(getPin());
  }
})();
