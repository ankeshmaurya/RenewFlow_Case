import {api} from "../api.js";
import {esc, $, $$, inr, fmtDt, chips, emptyNoData, decisionBadge, table, studentName} from "../util.js";
import {getResults, state} from "../state.js";
import {openCase, setOnChange} from "../components/drawer.js";
import {toast, guard} from "../ui.js";

export async function render(root) {
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  const cs = res.cases.filter((c) => c.decision === "AUTO_APPROVE");
  const done = cs.filter((c) => c.approved).length;
  const rowsTotal = cs.reduce((a, c) => a + c.proposed_rows.length, 0);
  root.innerHTML = `
    <div class="row between"><div><h1>Auto-approved queue</h1><p class="muted">${cs.length} renewals the engine can approve with no human touch, with ${rowsTotal} proposed class_schedule_bookings rows. ${done} approved (simulated).</p></div>
      <div class="row no-print"><button class="btn primary" id="apprAll" ${cs.length === done ? "disabled" : ""}>Approve all</button><a class="btn" href="/api/export/auto-approved.csv">Export CSV of proposed rows</a></div></div>
    ${cs.length ? cs.map((c) => `
      <div class="card"><div class="row between"><div><b><button class="linklike" data-id="${c.invoice.id}">Invoice ${esc(c.invoice.id)}</button></b>
        <span class="muted small">${esc(studentName(c.reference))} | ${esc(c.reference ? c.reference.classbatch_name : "")} | ${inr(c.invoice.net_amount)}</span></div>
        <div class="row no-print">${c.approved ? '<span class="badge">Approved (simulated)</span>' : `<button class="btn small primary" data-appr="${c.invoice.id}">Approve</button>`}</div></div>
        ${chips(c.reason_codes, state.codes)}
        ${c.provisional ? '<p class="diff small">Provisional: only the paid share of sessions is scheduled.</p>' : ""}
        ${c.healed_actions.length ? "<ul class='small'>" + c.healed_actions.map((h) => `<li>${esc(h)}</li>`).join("") + "</ul>" : ""}
        <p class="small">${esc(c.recommended_action)} ${c.proposed_booking_request ? "A new booking request will also be created." : "Uses existing booking request " + esc(c.booking.id) + "."}</p>
        <details><summary>${c.proposed_rows.length} proposed rows</summary>${table(["Date", "Start", "End", "Batch", "Booking request", "Type"], c.proposed_rows.map((r) =>
          [esc(r.class_date), esc(r.start_time), esc(r.end_time), esc(r.classbatch_id), esc(r.bookingrequest_id ?? "new"), esc(r.booking_type)]), "rt")}</details></div>`).join("") : '<div class="empty">No cases are auto-approvable right now.</div>'}`;
  $$("button.linklike[data-id]", root).forEach((b) => b.addEventListener("click", () => openCase(+b.dataset.id, b)));
  $$("button[data-appr]", root).forEach((b) => b.addEventListener("click", () => guard(async () => { await api.post(`/api/cases/${b.dataset.appr}/approve`); toast("Approved (simulated)"); await render(root); })));
  const all = $("#apprAll");
  if (all) all.onclick = () => guard(async () => { const r = await api.post("/api/approve-all"); toast(`${r.approved} cases approved (simulated)`); await render(root); });
  setOnChange(() => render(root));
}
