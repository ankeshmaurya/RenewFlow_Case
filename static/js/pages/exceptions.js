import {api} from "../api.js";
import {esc, $, $$, inr, hrs, fmtDt, chips, emptyNoData, decisionBadge, srcBadge, OWNERS, studentName} from "../util.js";
import {getResults, getMessages, state} from "../state.js";
import {openCase, setOnChange} from "../components/drawer.js";
import {toast, guard} from "../ui.js";

const OPEN = ["FLAGGED", "BLOCKED", "FAST_TRACK_PENDING_PARENT"];

async function copy(text) {
  try { await navigator.clipboard.writeText(text); } catch (e) {
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  toast("Copied");
}

export async function render(root, query = {}) {
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  const [msgs, audit] = await Promise.all([getMessages(), api.get("/api/audit")]);
  const open = res.cases.filter((c) => OPEN.includes(c.decision));
  const owners = [...new Set(open.map((c) => c.display_owner))];
  const filter = query.owner || "";
  const groups = owners.filter((o) => !filter || o === filter);
  root.innerHTML = `
    <h1>Exceptions</h1>
    <p class="muted">Everything that needs a person or a parent, grouped by owner. SLA states are text: On track, Due soon, Breached.</p>
    <div class="row no-print" style="margin-bottom:.8rem"><span class="small">Filter by owner:</span>
      <a class="btn small ${!filter ? "primary" : ""}" href="#/exceptions">All (${open.length})</a>
      ${owners.map((o) => `<a class="btn small ${filter === o ? "primary" : ""}" href="#/exceptions?owner=${esc(o)}">${esc(OWNERS[o] || o)}</a>`).join("")}</div>
    ${groups.length ? groups.map((o) => `<div class="card"><h2>${esc(OWNERS[o] || o)} (${open.filter((c) => c.display_owner === o).length})</h2>
      ${open.filter((c) => c.display_owner === o).map((c) => item(c, msgs)).join("")}</div>`).join("") : '<div class="empty">No open exceptions.</div>'}
    <div class="card"><h2>Audit log</h2>${audit.length ? '<div class="scroll tall"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Invoice</th><th>Detail</th></tr></thead><tbody>' +
      audit.slice(0, 30).map((a) => `<tr><td>${esc(fmtDt(a.at))}</td><td>${esc(a.actor)}</td><td>${esc(a.action)}</td><td>${esc(a.invoice_id ?? "")}</td><td>${esc(a.detail)}</td></tr>`).join("") + "</tbody></table></div>" : '<p class="muted">No actions yet.</p>'}</div>`;

  function item(c, all) {
    const ms = all.filter((m) => m.invoice_id === c.invoice.id);
    return `<div class="card flat" data-inv="${c.invoice.id}">
      <div class="row between"><div><b><button class="linklike" data-open="${c.invoice.id}">Invoice ${esc(c.invoice.id)}</button></b> ${decisionBadge(c.decision)}
        <span class="small">${esc(studentName(c.reference))}, ${inr(c.invoice.net_amount)}</span></div>
        <div class="small"><b>${esc(c.sla.state)}</b>${c.sla.hours_open != null ? ", " + hrs(c.sla.hours_open) + " open" : ""}</div></div>
      ${chips(c.reason_codes, state.codes)}
      <p><b>${esc(c.recommended_action)}</b></p>
      ${c.sla.escalation ? `<p class="diff small">${esc(c.sla.escalation)}</p>` : ""}
      ${c.decision === "FAST_TRACK_PENDING_PARENT" ? `<p class="small">Waiting on parent. <button class="btn small primary no-print" data-parent="${c.invoice.id}">Simulate parent reply: continue same batch</button></p>` : ""}
      ${ms.map((m) => `<div class="msg"><div class="row between"><span class="small"><b>${esc(m.channel)}</b> to ${esc(m.recipient_label)} ${srcBadge(m.source)} <span class="tag">${esc(m.status)}</span></span>
        <span class="row no-print"><button class="btn small" data-copy="${esc(m.id)}">Copy</button><button class="btn small" data-sent="${esc(m.id)}">Mark sent (simulated)</button></span></div>
        <p class="small" style="white-space:pre-wrap">${esc(m.body)}</p></div>`).join("")}
      <div class="row no-print"><div class="field" style="min-width:170px"><label for="ow_${c.invoice.id}">Reassign owner</label><select id="ow_${c.invoice.id}" data-owner="${c.invoice.id}">
        ${Object.entries(OWNERS).map(([k, v]) => `<option value="${k}" ${k === c.display_owner ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
        <div class="field" style="flex:1;min-width:220px"><label for="nt_${c.invoice.id}">Resolution note</label><input id="nt_${c.invoice.id}" placeholder="What was done?"></div>
        <button class="btn small" data-note="${c.invoice.id}">Save note</button></div>
      ${c.notes.length ? "<ul class='small'>" + c.notes.map((n) => `<li>${esc(n.text)} <span class="muted">(${esc(fmtDt(n.at))})</span></li>`).join("") + "</ul>" : ""}</div>`;
  }

  $$("button[data-open]", root).forEach((b) => b.addEventListener("click", () => openCase(+b.dataset.open, b)));
  $$("button[data-parent]", root).forEach((b) => b.addEventListener("click", () => guard(async () => { await api.post(`/api/cases/${b.dataset.parent}/parent-reply`); toast("Parent replied. Case moved to Auto-Approved."); await render(root, query); })));
  $$("button[data-copy]", root).forEach((b) => b.addEventListener("click", () => copy(msgs.find((m) => m.id === b.dataset.copy).body)));
  $$("button[data-sent]", root).forEach((b) => b.addEventListener("click", () => guard(async () => { await api.post(`/api/messages/${encodeURIComponent(b.dataset.sent)}/status`, {status: "sent-simulated"}); toast("Marked sent (simulated)"); await render(root, query); })));
  $$("select[data-owner]", root).forEach((s) => s.addEventListener("change", () => guard(async () => { await api.post(`/api/cases/${s.dataset.owner}/reassign`, {owner: s.value}); toast("Owner changed"); await render(root, query); })));
  $$("button[data-note]", root).forEach((b) => b.addEventListener("click", () => guard(async () => {
    const t = $("#nt_" + b.dataset.note).value.trim(); if (!t) return;
    await api.post(`/api/cases/${b.dataset.note}/note`, {text: t}); toast("Note saved"); await render(root, query); })));
  setOnChange(() => render(root, query));
}
