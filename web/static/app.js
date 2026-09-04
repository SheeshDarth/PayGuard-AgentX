/* PayGuard-AgentX operator dashboard.
   Vanilla JS, no framework, no external requests. All state comes from the
   Python API; this file renders it and sends decisions back. */

"use strict";

const state = { boot: null, run: null, records: null, role: null, evidenceSel: null,
                tamper: false, caseQuery: "" };

/* ───────────────────────────── helpers ───────────────────────────── */
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
/* Everything user- or pipeline-supplied goes through here before it touches
   innerHTML, so a supplier id or clause text can never inject markup. */
const esc = (v) => String(v ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const SYMBOL = { USD: "$", EUR: "€", INR: "₹" };
const money = (amount, currency) =>
  amount === null || amount === undefined ? null
    : (SYMBOL[currency] || "") + Number(amount).toLocaleString(undefined,
        { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const titled = (s) => String(s ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { node.hidden = true; }, 2600);
}

async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

/* Build a <details> disclosure with a rendered body. */
function disclosure(summary, buildBody, open) {
  const d = el("details", "disclosure");
  if (open) d.open = true;
  d.appendChild(el("summary", null, summary));
  const body = el("div", "disclosure-body");
  buildBody(body);
  d.appendChild(body);
  return d;
}

function jsonBlock(value) {
  const pre = el("pre", "json", JSON.stringify(value, null, 2));
  return pre;
}

function empty(title, message, hint) {
  const box = el("div", "empty");
  box.appendChild(el("h3", null, title));
  box.appendChild(el("p", null, message));
  if (hint) {
    const h = el("p", "hint muted");
    h.innerHTML = hint;
    box.appendChild(h);
  }
  return box;
}

function table(columns, rows) {
  const wrap = el("div", "table-wrap");
  const t = el("table");
  const thead = el("thead");
  const hr = el("tr");
  columns.forEach((c) => {
    const th = el("th", c.wrap ? "wrap" : null, c.label);
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  t.appendChild(thead);
  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((c) => {
      const value = c.get(row);
      tr.appendChild(el("td", [c.num ? "num" : "", c.wrap ? "wrap" : ""].join(" ").trim() || null,
                        value === null || value === undefined ? "—" : String(value)));
    });
    tbody.appendChild(tr);
  });
  t.appendChild(tbody);
  wrap.appendChild(t);
  return wrap;
}

/* ───────────────────────────── shared blocks ───────────────────────────── */
function whyPanel(why) {
  const box = el("div");
  if (!why || !why.reasons || !why.reasons.length) {
    box.appendChild(el("p", "muted fine", "The engine recorded no additional signals for this item."));
    return box;
  }
  const ul = el("ul", "why-list");
  why.reasons.forEach((r) => ul.appendChild(el("li", null, r)));
  box.appendChild(ul);

  const foot = el("div", "why-foot");
  if (why.score !== null && why.score !== undefined) {
    const scoreBox = el("div", "score-box");
    scoreBox.appendChild(el("div", "kpi-label", why.score_label || "Score"));
    scoreBox.appendChild(el("div", "score-val", `${why.score} / 100`));
    // Only a risk score maps onto the severity scale -- a high *confidence* is a
    // good sign, so colouring it like a high risk would read backwards.
    if (why.score_label === "Risk score") {
      const level = why.score >= 60 ? "high" : why.score >= 30 ? "medium" : "low";
      scoreBox.appendChild(el("span", `chip ${level}`, level.toUpperCase()));
    }
    foot.appendChild(scoreBox);
  }
  if (why.recommendation) {
    const rec = el("div", "rec-box");
    rec.appendChild(el("div", "kpi-label", "Recommendation"));
    rec.appendChild(el("div", null, why.recommendation));
    rec.appendChild(el("div", "fine", "Recommended only. Nothing is actioned until a person decides."));
    foot.appendChild(rec);
  }
  box.appendChild(foot);
  return box;
}

/* Text ladder of an account walk; a closing cycle is drawn back to the top
   rather than pretending the chain simply ends. */
function flowMap(chain, closesCycle) {
  const flow = el("div", "flow");
  if (!chain || !chain.length) return flow;
  const lines = [`<span class="node">${esc(chain[0])}</span>`];
  for (let i = 1; i < chain.length; i++) {
    lines.push("  ↓");
    lines.push(`<span class="node">${esc(chain[i])}</span>`);
  }
  if (closesCycle) {
    lines.push("  ↓");
    lines.push(`<span class="loop">  └──→ back to ${esc(chain[0])}  (closed loop)</span>`);
  }
  flow.innerHTML = lines.join("\n");
  return flow;
}

function networkGraph(ring) {
  const figure = el("figure", "network-figure");
  const caption = el("figcaption", "eyebrow", "Payment relationship graph");
  figure.appendChild(caption);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 720 280");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${ring.pattern_type} network containing ${ring.member_accounts.length} accounts`);
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", `arrow-${ring.ring_id}`);
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9"); marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "6"); marker.setAttribute("markerHeight", "6");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrow = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z"); arrow.setAttribute("class", "graph-arrow");
  marker.appendChild(arrow); defs.appendChild(marker); svg.appendChild(defs);
  const nodes = [...new Set((ring.edges || []).flatMap((e) => [e.sender, e.receiver]).concat(ring.member_accounts || []))];
  const points = new Map();
  const cx = 360, cy = 140, radius = Math.min(105, 48 + nodes.length * 9);
  nodes.forEach((name, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i / Math.max(nodes.length, 1));
    points.set(name, [cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius]);
  });
  (ring.edges || []).forEach((edge) => {
    const from = points.get(edge.sender), to = points.get(edge.receiver);
    if (!from || !to) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", from[0]); line.setAttribute("y1", from[1]);
    line.setAttribute("x2", to[0]); line.setAttribute("y2", to[1]);
    line.setAttribute("class", "graph-edge"); line.setAttribute("marker-end", `url(#arrow-${ring.ring_id})`);
    svg.appendChild(line);
  });
  points.forEach((point, name) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", point[0]); circle.setAttribute("cy", point[1]); circle.setAttribute("r", "23");
    circle.setAttribute("class", "graph-node"); group.appendChild(circle);
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", point[0]); label.setAttribute("y", point[1] + 4);
    label.setAttribute("text-anchor", "middle"); label.setAttribute("class", "graph-label");
    label.textContent = name; group.appendChild(label); svg.appendChild(group);
  });
  figure.appendChild(svg);
  const note = el("p", "fine", ring.closes_cycle
    ? "Arrow direction shows the closed loop back to the originating account."
    : "Arrow direction shows the pass-through path between accounts and suppliers.");
  figure.appendChild(note);
  return figure;
}

function timelineBlock(steps) {
  const wrap = el("div", "timeline");
  const MARK = { done: "✓", skipped: "–", pending: "⏳" };
  steps.forEach((step, i) => {
    const row = el("div", `tl-step tl-${step.status}`);
    row.appendChild(el("span", "tl-mark", MARK[step.status] || "·"));
    const body = el("span");
    body.appendChild(el("span", "tl-name", step.name));
    const detail = step.status === "skipped"
      ? `  (skipped — ${step.detail})`
      : `  ${step.detail}`;
    body.appendChild(el("span", "tl-detail", detail));
    row.appendChild(body);
    wrap.appendChild(row);
    if (i < steps.length - 1) wrap.appendChild(el("div", "tl-arrow", "↓"));
  });
  return wrap;
}

/* ───────────────────────────── views ───────────────────────────── */
function renderStatus() {
  const status = state.boot.status;
  const list = $("#status-list");
  list.replaceChildren();
  status.rows.forEach(([name, ok, detail]) => {
    const li = el("li");
    li.appendChild(el("span", "dot", ok ? "✓" : "✗"));
    const text = el("span");
    text.appendChild(el("span", "nm", name));
    text.appendChild(document.createTextNode(" · " + detail));
    li.appendChild(text);
    list.appendChild(li);
  });
  $("#status-llm").textContent = status.llm;
  $("#status-mode").textContent = status.mode;
}

function renderKpis() {
  const k = state.run ? state.run.kpis
    : { processed: 0, fraud_flags: 0, pending: 0, quarantined: 0,
        evidence: state.records ? state.records.evidence.length : 0 };
  const cards = [
    ["Processed", k.processed, "Records that passed the DQ gate"],
    ["Fraud flags", k.fraud_flags, "Invoice flags plus confirmed rings"],
    ["Pending", k.pending, "Actions waiting on a person"],
    ["Quarantined", k.quarantined, "Records the DQ-Sentinel refused"],
    ["Evidence", k.evidence, "Signed HMAC-SHA256 dossiers"],
  ];
  const host = $("#kpis");
  host.replaceChildren();
  cards.forEach(([label, value, help]) => {
    const card = el("div", "kpi");
    card.appendChild(el("div", "kpi-label", label));
    card.appendChild(el("div", "kpi-value", value));
    card.appendChild(el("div", "kpi-help", help));
    host.appendChild(card);
  });
  const badge = $("#nav-pending");
  badge.textContent = k.pending;
  badge.hidden = !k.pending;
}

function actionCard(action) {
  const level = action.priority.toLowerCase();
  const card = el("article", `card p-${level}`);

  const head = el("div", "card-head");
  const left = el("div");
  const kind = el("div", "card-kind");
  kind.appendChild(el("span", `chip ${level}`, action.priority));
  kind.appendChild(document.createTextNode(" " + action.type));
  left.appendChild(kind);

  const meta = el("div", "card-meta");
  const addMeta = (label, value) => {
    if (value === null || value === undefined) return;
    const span = el("span");
    span.appendChild(document.createTextNode(label + ": "));
    span.appendChild(el("b", null, value));
    meta.appendChild(span);
  };
  addMeta(action.entity_label, action.entity);
  addMeta("Amount", money(action.amount, action.currency));
  if (action.risk !== null && action.risk !== undefined) addMeta("Risk", `${action.risk}/100`);
  else if (action.confidence !== null && action.confidence !== undefined) {
    addMeta("Confidence", Math.round(action.confidence * 100) + "%");
  }
  left.appendChild(meta);
  head.appendChild(left);
  head.appendChild(el("span", "chip plain", action.status));
  card.appendChild(head);

  const body = el("div", "card-body");
  const reason = el("div", "field");
  reason.appendChild(el("span", "lbl", "Reason"));
  reason.appendChild(document.createTextNode(action.reason));
  body.appendChild(reason);

  const rec = el("div", "field");
  rec.appendChild(el("span", "lbl", "Recommended"));
  rec.appendChild(document.createTextNode(action.recommended));
  body.appendChild(rec);

  body.appendChild(disclosure("Why this was flagged", (host) => {
    host.appendChild(whyPanel(action.why));
    if (action.chain) host.appendChild(flowMap(action.chain, action.closes_cycle));
    host.appendChild(disclosure("Raw signals", (inner) => inner.appendChild(jsonBlock(action.raw))));
  }));
  card.appendChild(body);

  const allowed = canDecide(action.kind);
  const row = el("div", "btn-row");
  row.style.marginTop = ".9rem";
  const approve = el("button", "btn btn-primary", action.approve_label);
  const reject = el("button", "btn", action.reject_label);
  approve.disabled = reject.disabled = !allowed;
  approve.addEventListener("click", () => decide(approve, action, action.approve_action));
  reject.addEventListener("click", () => decide(reject, action, action.reject_action));
  row.append(approve, reject);
  card.appendChild(row);

  card.appendChild(el("p", "fine", allowed
    ? "Your decision is recorded and signed. It does not execute a payment or send a purchase order."
    : `Your role (${state.boot.user.role}) cannot decide this item. Change the demo role in Settings.`));
  return card;
}

function canDecide(kind) {
  const row = state.boot.capabilities.find((c) => c.role === state.boot.user.role);
  if (!row) return false;
  return kind === "RING" ? row.review_fraud : row.approve_po;
}

async function decide(button, action, verdict) {
  button.classList.add("is-busy");
  button.disabled = true;
  try {
    const data = await api("/api/decide", {
      kind: action.kind, id: action.id, action: verdict, role: state.boot.user.role,
    });
    state.run = data.run;
    state.records = data.records;
    state.boot.records = data.records;
    toast(`${titled(action.kind)} ${verdict.toLowerCase()} · decision signed`);
    renderAll();
  } catch (err) {
    button.classList.remove("is-busy");
    button.disabled = false;
    toast(err.message);
  }
}

function renderInbox() {
  const host = $("#actions");
  host.replaceChildren();
  if (state.run?.enterprise) {
    const enterprise = el("div", "enterprise-banner");
    const context = state.run.enterprise.retailer_context || {};
    enterprise.appendChild(el("div", "eyebrow", "Enterprise workspace"));
    enterprise.appendChild(el("h3", null, context.name || "Retail operating profile"));
    enterprise.appendChild(el("p", null, context.data_note || ""));
    const active = (state.run.enterprise.team_plan || []).filter((team) => team.status === "ACTIVE");
    enterprise.appendChild(el("p", "fine", `Active agent teams: ${active.map((team) => team.name).join(" · ") || "Enterprise Control Team"}`));
    host.appendChild(enterprise);
  }
  if (!state.run) {
    host.appendChild(empty("Nothing is waiting",
      "No analysis has been run in this session yet.",
      "Pick a demo scenario above and select <strong>Run demo</strong> to start."));
  } else if (!state.run.actions.length) {
    host.appendChild(empty("No pending actions",
      "Every procurement and fraud decision from this run has been reviewed.",
      "Pick another scenario, or select <strong>Reset</strong> above to run this one again from a clean queue."));
  } else {
    state.run.actions.forEach((a) => host.appendChild(actionCard(a)));
  }

  const tlBlock = $("#timeline-block");
  tlBlock.hidden = !state.run;
  if (state.run) {
    $("#route-note").innerHTML =
      `Supervisor route for this run: <strong>${esc(state.run.route)}</strong> — the route decides which agents are needed.`;
    $("#timeline").replaceChildren(...timelineBlock(state.run.timeline).childNodes);
  }

  const alerts = $("#alerts");
  alerts.replaceChildren();
  const list = state.run ? state.run.alerts : [];
  if (!list.length) {
    alerts.appendChild(state.run
      ? empty("No open investigations",
              "This run produced no invoice or network alert that needs a case.",
              "Run the <strong>Suspicious Invoice</strong> or <strong>Fraud Ring</strong> scenario to raise one.")
      : empty("No investigations yet",
              "Run the Fraud Ring scenario to explore network-level detection."));
    return;
  }
  list.forEach((alert) => {
    const level = (alert.severity || "LOW").toLowerCase();
    const card = el("article", `card p-${level}`);
    const head = el("div", "card-head");
    const left = el("div");
    left.appendChild(el("div", "card-kind", alert.title));
    left.appendChild(el("p", "muted", alert.summary));
    left.appendChild(el("p", "fine", `Type: ${titled(alert.alert_type)} · Subject: ${alert.subject_id}`));
    head.appendChild(left);
    head.appendChild(el("span", `chip ${level}`, alert.severity));
    card.appendChild(head);
    alerts.appendChild(card);
  });
}

function renderOperations() {
  const host = $("#operations");
  host.replaceChildren();
  if (!state.run) {
    host.appendChild(empty("No analysis yet",
      "Operations shows the retail side of the most recent run: what is low on stock, what the agents propose ordering, and how the returning invoices checked out.",
      "Run the <strong>Normal Restock</strong> scenario from the Action Inbox."));
    return;
  }
  const ops = state.run.operations;

  if (state.run.dataset && state.run.dataset.label !== "Synthetic demo data") {
    const source = el("div", "alert alert-ok");
    source.appendChild(el("strong", null, state.run.dataset.label));
    source.appendChild(document.createTextNode(" — " + state.run.dataset.lineage));
    host.appendChild(source);
  }

  const kpis = el("div", "kpis");
  [["Low-stock items", ops.stock_alerts.length],
   ["Purchase order", ops.po ? "Drafted" : "None"],
   ["Order value", ops.po ? money(ops.po.total_estimated_cost, ops.po.currency) : "—"],
   ["Invoice flags", ops.flags.length]].forEach(([label, value]) => {
    const card = el("div", "kpi");
    card.appendChild(el("div", "kpi-label", label));
    card.appendChild(el("div", "kpi-value", value));
    kpis.appendChild(card);
  });
  host.appendChild(kpis);

  host.appendChild(el("h3", "section-sub", "Inventory and replenishment"));
  if (ops.stock_alerts.length) {
    const visibleAlerts = ops.stock_alerts.slice(0, 25);
    const lead = el("div", "replenishment-lead");
    lead.appendChild(el("div", "eyebrow", "What should be restocked"));
    lead.appendChild(el("h3", null, `${visibleAlerts.length} replenishment recommendation${visibleAlerts.length === 1 ? "" : "s"}`));
    lead.appendChild(el("p", "muted", "These are the highest-demand Walmart store/department pairs identified by the Stock-Watcher. The quantity is a recommendation, not an executed order."));
    const leadList = el("div", "replenishment-list");
    visibleAlerts.slice(0, 5).forEach((r) => {
      const item = el("div", "replenishment-item");
      item.appendChild(el("strong", null, r.item_name || r.sku));
      item.appendChild(el("span", "muted", `${r.store_id} · order ${Number(r.recommend_order_qty).toLocaleString()} · demand ${Number(r.projected_demand).toLocaleString()}`));
      leadList.appendChild(item);
    });
    lead.appendChild(leadList);
    host.appendChild(lead);
    host.appendChild(table([
      { label: "Item / department", wrap: true, get: (r) => `${r.item_name || r.sku} (${r.sku})` },
      { label: "Store", get: (r) => r.store_id },
      { label: "On hand", num: true, get: (r) => r.on_hand },
      { label: "Projected demand", num: true, get: (r) => r.projected_demand },
      { label: "Recommended order", num: true, get: (r) => r.recommend_order_qty },
      { label: "Why", wrap: true, get: (r) => r.rationale },
    ], visibleAlerts));
    if (ops.stock_alerts.length > visibleAlerts.length) {
      host.appendChild(el("p", "fine muted", `Showing the 25 highest-demand recommendations of ${ops.stock_alerts.length}. The complete batch remains in the signed PO and raw technical detail.`));
    }
  } else {
    host.appendChild(empty("Inventory looks healthy",
      "Nothing in this run fell below its reorder point or projected demand."));
  }

  host.appendChild(el("h3", "section-sub", "Purchase order"));
  if (ops.po) {
    const card = el("div", "card p-low");
    const head = el("div", "card-head");
    const left = el("div");
    left.appendChild(el("div", "card-kind", ops.po.po_id));
    const meta = el("div", "card-meta");
    meta.innerHTML = `<span>Value: <b>${esc(money(ops.po.total_estimated_cost, ops.po.currency))}</b></span>` +
      `<span>Status: <b>${esc(ops.po.status || "DRAFT")}</b></span>` +
      `<span>Lines: <b>${ops.po.lines.length}</b></span>`;
    left.appendChild(meta);
    head.appendChild(left);
    head.appendChild(el("span", "chip medium", "NEEDS HUMAN APPROVAL"));
    card.appendChild(head);
    const visibleLines = ops.po.lines.slice(0, 25);
    card.appendChild(table([
      { label: "Item / department", wrap: true, get: (r) => `${r.item_name || r.sku} (${r.sku})` },
      { label: "Store", get: (r) => r.store_id },
      { label: "On hand", num: true, get: (r) => r.current_on_hand },
      { label: "Order qty", num: true, get: (r) => r.recommend_order_qty },
      { label: "Rationale", wrap: true, get: (r) => r.rationale },
    ], visibleLines));
    if (ops.po.lines.length > visibleLines.length) {
      card.appendChild(el("p", "fine muted", `Showing 25 of ${ops.po.lines.length} purchase-order lines in the demo view.`));
    }
    card.appendChild(disclosure("Why this order was proposed",
      (b) => { b.appendChild(whyPanel(ops.po_why)); }, true));
    card.appendChild(disclosure("Raw purchase order", (b) => b.appendChild(jsonBlock(ops.po))));
    card.appendChild(el("p", "fine",
      "Approve or reject this order from the Action Inbox. Approval records a decision; it never sends the order or moves money."));
    host.appendChild(card);
  } else {
    host.appendChild(empty("No purchase order",
      "No replenishment was required for this run, so the Ops-Planner drafted nothing."));
  }

  host.appendChild(el("h3", "section-sub", "Supplier invoice checks"));
  if (ops.flags.length) {
    ops.flags.forEach((flag) => {
      const card = el("div", "card p-high");
      card.appendChild(el("div", "eyebrow", titled(flag.flag_type)));
      card.appendChild(el("div", "card-kind", flag.description));
      card.appendChild(el("p", "fine", `Invoice: ${flag.invoice_id} · Severity: ${flag.severity || "—"}`));
      card.appendChild(disclosure("Why this was flagged", (b) => b.appendChild(whyPanel(flag.why))));
      host.appendChild(card);
    });
  } else {
    host.appendChild(empty("No invoice problems", ops.clean_invoices
      ? `${ops.clean_invoices} invoice(s) passed the payment audit with no mismatch or duplicate.`
      : "No supplier invoices were part of this run."));
  }

  if (ops.rejected.length) {
    host.appendChild(el("h3", "section-sub", "Quarantined at the gate"));
    host.appendChild(el("p", "fine",
      "The DQ-Sentinel refused these records before any agent reasoned over them."));
    host.appendChild(table([
      { label: "Stream", get: (r) => r.kind },
      { label: "Reason", wrap: true, get: (r) => r.note },
    ], ops.rejected));
  }
}

function renderAnalyst() {
  const host = $("#analyst");
  host.replaceChildren();
  if (!state.run) {
    host.appendChild(empty("No investigation yet",
      "This workspace shows the network-level fraud layer: which accounts are linked, what pattern connects them, and what each signal contributed.",
      "Run the <strong>Fraud Ring</strong> scenario from the Action Inbox."));
    return;
  }
  const fraud = state.run.fraud;
  if (!fraud.rings.length) {
    host.appendChild(empty("No fraud rings detected",
      "The Ring-Auditor scanned this run's payment graph and confirmed no ring. That is a clean result, not a missing feature.",
      "Run the <strong>Fraud Ring</strong> scenario to explore network-level detection."));
    return;
  }

  const kpis = el("div", "kpis");
  [["Fraud rings", fraud.rings.length],
   ["Suspicious accounts", fraud.accounts.length],
   ["Highest risk", Math.max(...fraud.rings.map((r) => r.risk_score)) + "/100"]]
    .forEach(([label, value]) => {
      const card = el("div", "kpi");
      card.appendChild(el("div", "kpi-label", label));
      card.appendChild(el("div", "kpi-value", value));
      kpis.appendChild(card);
    });
  host.appendChild(kpis);

  const control = el("div", fraud.payroll_flagged ? "alert alert-warn" : "alert alert-ok");
  control.innerHTML = fraud.payroll_flagged
    ? "<strong>False-positive control</strong>The seeded payroll run <em>was</em> flagged — the suppressor did not hold on this graph."
    : "<strong>False-positive control</strong>A legitimate payroll run (12 identical payments to 12 payees) is seeded into the same graph and was correctly <em>not</em> flagged.";
  host.appendChild(control);

  if (fraud.scan_truncated) {
    const warn = el("div", "alert alert-warn");
    warn.innerHTML = "<strong>Partial scan</strong>The cycle scan hit its time budget. These results are a subset of the graph, not proof that no other rings exist.";
    host.appendChild(warn);
  }

  fraud.rings.forEach((ring) => {
    const level = ring.risk_score >= 60 ? "high" : "medium";
    const card = el("article", `card p-${level}`);
    const head = el("div", "card-head");
    const left = el("div");
    left.appendChild(el("div", "card-kind", `${ring.ring_id} · ${titled(ring.pattern_type)}`));
    left.appendChild(el("p", "muted",
      `Connects ${ring.member_accounts.length} accounts with a risk score of ${ring.risk_score.toFixed(1)}/100. ` +
      (ring.risk_score >= 60 ? "Queued for human review." : "Monitored only.")));
    head.appendChild(left);
    head.appendChild(el("span", `chip ${level}`, level.toUpperCase()));
    card.appendChild(head);

    const grid = el("div", "grid-2");
    grid.style.marginTop = ".8rem";
    const mapCol = el("div");
    mapCol.appendChild(el("div", "eyebrow", "Detected relationship"));
    mapCol.appendChild(flowMap(ring.chain, ring.closes_cycle));
    grid.appendChild(mapCol);

    const memCol = el("div");
    memCol.appendChild(el("div", "eyebrow", "Accounts in this ring"));
    const ul = el("ul", "list-plain");
    ring.members.forEach((m) => {
      const li = el("li");
      li.appendChild(el("b", null, m.account_id));
      li.appendChild(document.createTextNode(m.score === null
        ? " — no individual signal above threshold"
        : ` — score ${m.score}, signals: ${m.patterns.join(", ")}`));
      ul.appendChild(li);
    });
    memCol.appendChild(ul);
    grid.appendChild(memCol);
    card.appendChild(grid);
    card.appendChild(networkGraph(ring));

    if (ring.edges.length) {
      card.appendChild(el("div", "eyebrow", "Transactions inside the ring"));
      card.appendChild(table([
        { label: "From", get: (r) => r.sender },
        { label: "To", get: (r) => r.receiver },
        { label: "Amount", num: true, get: (r) => Number(r.amount).toLocaleString() },
        { label: "When", get: (r) => String(r.timestamp).replace("T", " ").slice(0, 16) },
      ], ring.edges));
    }
    card.appendChild(disclosure("Why this was flagged", (b) => b.appendChild(whyPanel(ring.why))));
    card.appendChild(disclosure("Detection signals", (b) => b.appendChild(jsonBlock({
      ring_id: ring.ring_id, pattern_type: ring.pattern_type, risk_score: ring.risk_score,
      confidence: ring.confidence, member_accounts: ring.member_accounts,
    }))));
    host.appendChild(card);
  });

  host.appendChild(el("h3", "section-sub", "All scored accounts"));
  host.appendChild(table([
    { label: "Account", get: (r) => r.account_id },
    { label: "Score", num: true, get: (r) => r.suspicion_score },
    { label: "Ring", get: (r) => r.ring_id },
    { label: "Patterns", wrap: true, get: (r) => r.detected_patterns.join(", ") },
  ], fraud.accounts));

  if (fraud.transactions.length) {
    host.appendChild(disclosure("Full payment graph", (b) => b.appendChild(table([
      { label: "Tx", get: (r) => r.tx_id },
      { label: "From", get: (r) => r.sender },
      { label: "To", get: (r) => r.receiver },
      { label: "Amount", num: true, get: (r) => Number(r.amount).toLocaleString() },
      { label: "When", get: (r) => String(r.timestamp).replace("T", " ").slice(0, 16) },
    ], fraud.transactions))));
  }
}

function renderCases() {
  const host = $("#cases");
  host.replaceChildren();
  const cases = state.records.cases;
  if (!cases.length) {
    host.appendChild(empty("No cases yet",
      "A case is opened automatically for every alert an analysis raises, and its status follows the decision you record.",
      "Run any demo scenario to create the first case."));
    return;
  }
  const counts = cases.reduce((acc, c) => {
    const s = c.status || "OPEN";
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});
  const kpis = el("div", "kpis");
  [["Total", cases.length], ["Open", counts.OPEN || 0], ["Escalated", counts.ESCALATED || 0],
   ["Closed", (counts.RESOLVED || 0) + (counts.DISMISSED || 0)]].forEach(([l, v]) => {
    const card = el("div", "kpi");
    card.appendChild(el("div", "kpi-label", l));
    card.appendChild(el("div", "kpi-value", v));
    kpis.appendChild(card);
  });
  host.appendChild(kpis);

  const q = state.caseQuery.toLowerCase();
  const filtered = cases.filter((c) => !q ||
    (`${c.title} ${c.summary} ${(c.related_ids || []).join(" ")}`).toLowerCase().includes(q));
  host.appendChild(el("p", "fine", `Showing ${filtered.length} of ${cases.length} case(s)`));
  if (!filtered.length) {
    host.appendChild(empty("No matching cases", `Nothing matches “${state.caseQuery}”.`,
      "Clear the search to see all cases."));
    return;
  }
  filtered.forEach((c) => {
    const level = (c.severity || "LOW").toLowerCase();
    const card = el("article", `card p-${level}`);
    const head = el("div", "card-head");
    const left = el("div");
    left.appendChild(el("div", "card-kind", c.title));
    left.appendChild(el("p", "muted", c.summary));
    left.appendChild(el("p", "fine",
      `${c.case_id} · Status: ${c.status || "OPEN"} · Related: ${(c.related_ids || []).join(", ") || "—"}`));
    head.appendChild(left);
    head.appendChild(el("span", `chip ${level}`, c.severity || "LOW"));
    card.appendChild(head);
    host.appendChild(card);
  });
}

function renderEvidence() {
  const host = $("#evidence");
  host.replaceChildren();
  const evidence = state.records.evidence;
  if (!evidence.length) {
    host.appendChild(empty("No evidence yet",
      "Every consequential action — a purchase order, a dispute, a fraud ring, and each operator decision — is sealed into an HMAC-SHA256 signed dossier.",
      "Run any demo scenario to create signed evidence."));
    return;
  }
  const valid = evidence.filter((e) => e.valid).length;
  const kpis = el("div", "kpis");
  [["Evidence records", evidence.length], ["Signatures valid", `${valid}/${evidence.length}`],
   ["Algorithm", "HMAC-SHA256"]].forEach(([l, v]) => {
    const card = el("div", "kpi");
    card.appendChild(el("div", "kpi-label", l));
    card.appendChild(el("div", "kpi-value", v));
    kpis.appendChild(card);
  });
  host.appendChild(kpis);
  host.appendChild(el("p", "fine",
    "A signature is computed over a canonical form of the payload with a server-held key, so a payload cannot be edited after the fact without breaking the seal."));

  host.appendChild(table([
    { label: "Evidence ID", get: (r) => r.evidence_id },
    { label: "Subject", get: (r) => r.subject_id },
    { label: "Type", get: (r) => r.evidence_type },
    { label: "Signature", get: (r) => (r.valid ? "valid" : "INVALID") },
  ], evidence));

  if (!state.evidenceSel || !evidence.some((e) => e.evidence_id === state.evidenceSel)) {
    state.evidenceSel = evidence[0].evidence_id;
  }
  const panel = el("div", "panel");
  panel.appendChild(el("div", "eyebrow", "Evidence dossier"));

  const picker = el("select", "select");
  evidence.forEach((e) => {
    const opt = el("option", null, e.evidence_id);
    opt.value = e.evidence_id;
    if (e.evidence_id === state.evidenceSel) opt.selected = true;
    picker.appendChild(opt);
  });
  picker.addEventListener("change", () => {
    state.evidenceSel = picker.value;
    state.tamper = false;
    renderEvidence();
  });
  panel.appendChild(picker);

  const item = evidence.find((e) => e.evidence_id === state.evidenceSel);
  const dossier = state.tamper
    ? { ...item.dossier, payload: { ...item.dossier.payload, _injected: "attacker-controlled" } }
    : item.dossier;

  const dl = el("dl", "kv");
  [["Action", item.evidence_type], ["Case ID", item.evidence_id],
   ["Subject", item.subject_id || "—"], ["Created", dossier.timestamp || "—"]]
    .forEach(([k, v]) => { dl.appendChild(el("dt", null, k)); dl.appendChild(el("dd", null, v)); });
  panel.appendChild(dl);

  const decision = el("div", "field");
  decision.appendChild(el("span", "lbl", "Decision"));
  decision.appendChild(document.createTextNode(dossier.summary || "—"));
  panel.appendChild(decision);

  panel.appendChild(disclosure("Evidence payload", (b) => b.appendChild(jsonBlock(dossier.payload))));

  const verifyRow = el("div", "btn-row");
  verifyRow.style.margin = ".9rem 0";
  const verifyBtn = el("button", "btn btn-primary", "Verify signature");
  const tamperBtn = el("button", "btn", state.tamper ? "Undo tamper" : "Demo: tamper with payload");
  verifyRow.append(verifyBtn, tamperBtn);
  panel.appendChild(verifyRow);

  const result = el("div", `alert ${state.tamper ? "alert-error" : "alert-ok"}`);
  result.innerHTML = state.tamper
    ? "<strong>Integrity: signature INVALID</strong>The payload no longer matches its signature. Editing the evidence cannot re-seal it, because the signing key is not in the payload."
    : (item.valid
      ? "<strong>Integrity: signature valid</strong>HMAC-SHA256 verified — payload unchanged since signing."
      : "<strong>Integrity: signature INVALID</strong>This stored record does not match its signature.");
  panel.appendChild(result);

  verifyBtn.addEventListener("click", async () => {
    verifyBtn.classList.add("is-busy");
    try {
      const data = await api("/api/verify",
        { evidence_id: state.evidenceSel, tamper: state.tamper });
      toast(data.valid ? "Signature verified on the server" : "Signature INVALID on the server");
    } catch (err) {
      toast(err.message);
    } finally {
      verifyBtn.classList.remove("is-busy");
    }
  });
  tamperBtn.addEventListener("click", () => { state.tamper = !state.tamper; renderEvidence(); });

  host.appendChild(panel);
}

function renderSettings() {
  const host = $("#settings");
  host.replaceChildren();

  const workspace = el("div", "panel");
  workspace.appendChild(el("div", "eyebrow", "Workspace"));
  const profile = state.boot.retailer_profiles.find((item) => item.id === $("#retailer-profile").value)
    || state.boot.retailer_profiles[0];
  workspace.appendChild(el("p", null, profile.name));
  workspace.appendChild(el("p", "fine",
    profile.data_note));
  host.appendChild(workspace);

  const access = el("div", "panel");
  access.appendChild(el("div", "eyebrow", "Access"));
  if (state.boot.demo_mode) {
    access.appendChild(el("label", "field-label", "Demo role"));
    const picker = el("select", "select");
    state.boot.roles.forEach((role) => {
      const opt = el("option", null, role);
      opt.value = role;
      if (role === state.boot.user.role) opt.selected = true;
      picker.appendChild(opt);
    });
    picker.addEventListener("change", () => changeRole(picker.value));
    access.appendChild(picker);
    access.appendChild(el("p", "fine",
      "The demo-role selector exists only because PAYGUARD_DEMO_MODE is on. Published mode uses OIDC/SSO, and the role comes from the identity provider."));
  } else {
    access.appendChild(el("p", null, `Signed in as ${state.boot.user.display_name} (${state.boot.user.role}).`));
  }
  access.appendChild(el("h3", "section-sub", "Roles and what they can decide"));
  access.appendChild(table([
    { label: "Role", get: (r) => r.role },
    { label: "Approve purchase orders", get: (r) => (r.approve_po ? "Yes" : "No") },
    { label: "Review fraud rings", get: (r) => (r.review_fraud ? "Yes" : "No") },
    { label: "Manage settings", get: (r) => (r.manage_settings ? "Yes" : "No") },
  ], state.boot.capabilities));
  access.appendChild(el("p", "fine",
    "Authorization is enforced on the server for every decision, not in the browser."));
  host.appendChild(access);

  const runtime = el("div", "panel");
  runtime.appendChild(el("div", "eyebrow", "Runtime"));
  const ul = el("ul", "status-list");
  state.boot.status.rows.forEach(([name, ok, detail]) => {
    const li = el("li");
    li.appendChild(el("span", "dot", ok ? "✓" : "✗"));
    const t = el("span");
    t.appendChild(el("span", "nm", name));
    t.appendChild(document.createTextNode(" · " + detail));
    li.appendChild(t);
    ul.appendChild(li);
  });
  runtime.appendChild(ul);
  runtime.appendChild(el("p", "fine",
    `LLM: ${state.boot.status.llm} · Mode: ${state.boot.status.mode}`));
  runtime.appendChild(el("p", "fine",
    "Every subsystem above has a tested offline fallback. The demo needs no API key, no GPU, and no network."));
  host.appendChild(runtime);

  const teams = el("div", "panel");
  teams.appendChild(el("div", "eyebrow", "Custom agent teams"));
  teams.appendChild(el("p", null,
    "Build a named team around existing specialists. Teams coordinate responsibility and visibility; they cannot change financial approval rules."));
  if (state.boot.user.role === "ADMIN") {
    const name = el("input", "input"); name.placeholder = "Team name, e.g. Freshness Response Team";
    const mission = el("input", "input"); mission.placeholder = "What this team owns and improves";
    const agentPicker = el("select", "select"); agentPicker.multiple = true; agentPicker.size = 6;
    (state.boot.agents || []).forEach((agent) => {
      const opt = el("option", null, agent.name); opt.value = agent.name; agentPicker.appendChild(opt);
    });
    const create = el("button", "btn btn-primary", "Create agent team");
    create.addEventListener("click", async () => {
      const agents = [...agentPicker.selectedOptions].map((option) => option.value);
      create.disabled = true;
      try {
        const data = await api("/api/teams", { name: name.value, mission: mission.value, agents,
          role: state.boot.user.role });
        state.boot.agent_teams = data.agent_teams;
        renderAll();
        toast("Custom agent team created");
      } catch (err) { toast(err.message); }
      finally { create.disabled = false; }
    });
    teams.append(name, mission, agentPicker, create);
  } else {
    teams.appendChild(el("p", "fine", "Switch to the Admin demo role to create a custom team. Published deployments require an administrator identity from OIDC/SSO."));
  }
  host.appendChild(teams);

  const guard = el("div", "alert alert-warn");
  guard.innerHTML = "<strong>Financial actions stay human-controlled</strong>No payment, supplier submission, or external financial execution is available from this product. Approving an action records a signed decision only.";
  host.appendChild(guard);
}

function renderAgents() {
  const host = $("#agents");
  if (!host) return;
  host.replaceChildren();
  const intro = el("div", "panel");
  intro.appendChild(el("div", "eyebrow", "How this is agentic"));
  intro.appendChild(el("p", null,
    "The supervisor selects a route, specialized agents transform evidence, critics review drafts, and the HITL controller stops consequential actions for a human decision."));
  intro.appendChild(el("p", "fine",
    "Deterministic checks decide what is safe to recommend. Optional LLM hooks explain, negotiate, critique, and draft; they never authorize payment."));
  host.appendChild(intro);
  const teamGrid = el("div", "team-grid");
  (state.boot.agent_teams || []).forEach((team) => {
    const card = el("article", "panel team-card");
    const plan = state.run?.enterprise?.team_plan?.find((item) => item.team_id === team.team_id);
    card.appendChild(el("div", "eyebrow", team.is_custom ? "Custom team" : "Operating team"));
    card.appendChild(el("h3", "section-sub", team.name));
    card.appendChild(el("p", null, team.mission));
    card.appendChild(el("p", "fine", `Agents: ${(team.agents || []).join(" · ")}`));
    if (plan) card.appendChild(el("span", `chip ${plan.status === "ACTIVE" ? "ok" : "plain"}`, plan.status));
    teamGrid.appendChild(card);
  });
  host.appendChild(el("h3", "section-sub", "Enterprise agent teams"));
  host.appendChild(teamGrid);
  host.appendChild(el("h3", "section-sub", "Specialist agent catalogue"));
  const grid = el("div", "agent-grid");
  (state.boot.agents || []).forEach((agent, index) => {
    const card = el("article", "panel agent-card");
    card.appendChild(el("div", "agent-number", String(index + 1).padStart(2, "0")));
    card.appendChild(el("h3", "section-sub", agent.name));
    card.appendChild(el("div", "chip low", agent.type));
    card.appendChild(el("p", null, agent.purpose));
    card.appendChild(el("p", "fine", agent.authority));
    grid.appendChild(card);
  });
  host.appendChild(grid);
}

/* ───────────────────────────── orchestration ───────────────────────────── */
function renderAll() {
  renderStatus();
  renderKpis();
  renderInbox();
  renderOperations();
  renderAnalyst();
  renderCases();
  renderEvidence();
  renderSettings();
  renderAgents();
  $("#who-name").textContent = state.boot.user.display_name;
  $("#who-role").textContent = state.boot.user.role;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
  // Demo controls belong to the inbox; the other views read the same run.
  $("#demo-panel").hidden = name !== "inbox";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderScenarioMeta() {
  const picked = state.boot.scenarios.find((s) => s.id === $("#scenario").value);
  if (!picked) return;
  $("#scenario-blurb").textContent = picked.blurb;
  const list = $("#scenario-demos");
  list.replaceChildren();
  picked.demonstrates.forEach((d) => list.appendChild(el("li", null, d)));
}

function renderRetailerMeta() {
  const picked = state.boot.retailer_profiles.find((item) => item.id === $("#retailer-profile").value);
  if (picked) $("#retailer-note").textContent = `${picked.name} · ${picked.data_note}`;
}

async function runDemo() {
  const button = $("#run-demo");
  button.classList.add("is-busy");
  button.disabled = true;
  $("#run-error").hidden = true;
  try {
    const data = await api("/api/run", { scenario: $("#scenario").value,
      retailer_profile: $("#retailer-profile").value });
    state.run = data.run;
    state.records = data.records;
    state.boot.records = data.records;
    renderAll();
    const scenarioId = String(state.boot.scenarios.find((s) => s.id === $("#scenario").value)?.id || "");
    showView(scenarioId.startsWith("1") || scenarioId.startsWith("5") ? "operations" : scenarioId.startsWith("3")
      ? "analyst" : "inbox");
    toast(`Analysis complete · route ${state.run.route}`);
  } catch (err) {
    const box = $("#run-error");
    box.innerHTML = "<strong>That scenario could not be completed.</strong>" +
      "The application stays in offline mode and your previous results are unchanged. " +
      "Try running the scenario again — the technical detail is in the server log.";
    box.hidden = false;
  } finally {
    button.classList.remove("is-busy");
    button.disabled = false;
  }
}

async function resetDemo() {
  const button = $("#reset-demo");
  button.classList.add("is-busy");
  try {
    const data = await api("/api/reset", { role: state.boot.user.role });
    state.run = null;
    state.records = data.records;
    state.boot.records = data.records;
    state.evidenceSel = null;
    state.tamper = false;
    renderAll();
    toast("Demo workspace cleared");
  } catch (err) {
    toast(err.message);
  } finally {
    button.classList.remove("is-busy");
  }
}

async function changeRole(role) {
  try {
    const boot = await api("/api/bootstrap", { role });
    state.boot = boot;
    state.records = boot.records;
    state.run = boot.run;
    renderAll();
    toast(`Acting as ${role}`);
  } catch (err) {
    toast(err.message);
  }
}

/* theme: auto -> light -> dark, remembered per browser */
function initTheme() {
  const order = ["auto", "light", "dark"];
  const label = { auto: "Auto theme", light: "Light theme", dark: "Dark theme" };
  let current = "auto";
  try { current = localStorage.getItem("payguard-theme") || "auto"; } catch (e) { /* private mode */ }
  const apply = () => {
    document.documentElement.setAttribute("data-theme", current);
    $("#theme-label").textContent = label[current];
  };
  apply();
  $("#theme-toggle").addEventListener("click", () => {
    current = order[(order.indexOf(current) + 1) % order.length];
    try { localStorage.setItem("payguard-theme", current); } catch (e) { /* ignore */ }
    apply();
  });
}

/* Ambient field behind the whole content column. auralis.js is a plain script
   tag, so guard the call: if that file ever fails to load the dashboard must
   still render, just on the flat theme background the CSS already paints. */
function initHero() {
  const canvas = $("#bg-canvas");
  if (!canvas || typeof mountAuralis !== "function") return;
  try {
    mountAuralis(canvas, { speed: 0.28, grain: 0.55 });
  } catch (err) {
    console.warn("Auralis background unavailable:", err);
  }
}

async function init() {
  initTheme();
  initHero();
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.addEventListener("click", () => showView(b.dataset.view)));
  $("#run-demo").addEventListener("click", runDemo);
  $("#reset-demo").addEventListener("click", resetDemo);
  $("#case-search").addEventListener("input", (e) => {
    state.caseQuery = e.target.value;
    renderCases();
  });

  try {
    state.boot = await api("/api/bootstrap");
  } catch (err) {
    document.querySelector(".main").prepend(Object.assign(el("div", "alert alert-error"), {
      innerHTML: "<strong>Could not reach the PayGuard server.</strong>" +
        "Start it with <code>python -m web.server</code> and reload this page.",
    }));
    return;
  }
  state.records = state.boot.records;
  state.run = state.boot.run;

  $("#hero-lede").textContent = state.boot.product.lede;
  const picker = $("#scenario");
  state.boot.scenarios.forEach((s) => {
    const opt = el("option", null, s.id);
    opt.value = s.id;
    picker.appendChild(opt);
  });
  picker.addEventListener("change", renderScenarioMeta);
  const retailerPicker = $("#retailer-profile");
  state.boot.retailer_profiles.forEach((profile) => {
    const opt = el("option", null, profile.name); opt.value = profile.id; retailerPicker.appendChild(opt);
  });
  retailerPicker.addEventListener("change", () => { renderRetailerMeta(); renderSettings(); });
  // A run survives a page reload on the server, so point the selector at the
  // scenario actually on screen rather than back at the first one.
  if (state.run && state.boot.scenarios.some((s) => s.id === state.run.preset)) {
    picker.value = state.run.preset;
  }
  if (state.run?.enterprise?.retailer_profile) retailerPicker.value = state.run.enterprise.retailer_profile;
  renderScenarioMeta();
  renderRetailerMeta();
  renderAll();
}

init();
