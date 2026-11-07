import {api} from "../api.js";
import {esc, $, fmtDt, inr, hrs, decisionBadge, chips, steps, kv, srcBadge, skeleton, studentName, parentName} from "../util.js";
import {state} from "../state.js";
import {toast, showError} from "../ui.js";

let onChange = () => {};
export function setOnChange(fn) { onChange = fn; }

export function closeDrawer() {
  $("#drawer").hidden = true; $("#drawerBackdrop").hidden = true;
  if (closeDrawer.opener) closeDrawer.opener.focus();
}

function formCard(c, f) {
  const suppressed = c.suppressed_form_ids.includes(f.id);
  const healed = c.healed_from_form_id === f.id;
  const tags = (suppressed ? '<span class="tag">DUPLICATE, SUPPRESSED</span>' : "") + (healed ? '<span class="tag">LINK HEALED</span>' : "") +
    (c.primary_form_id === f.id ? '<span class="tag">PRIMARY</span>' : "") + (f.source !== "teacher" ? '<span class="tag">PARENT REPLY</span>' : "");
  const body = kv({"Status": f.approval_status, "Amount paid": inr(f.amount_paid), "Invoice id typed": f.invoice_id, "Batch": f.current_classbatch_id,
    "Same batch": f.continue_same_batch, "Days": f.preferred_days, "Time": f.preferred_time_slot, "Remarks": f.remarks, "Created": fmtDt(f.created_at)});
  const heal = healed ? `<p class="diff small">Typed invoice <b>${esc(c.healed_typed_invoice_id)}</b> was matched to invoice <b>${esc(c.invoice.id)}</b>.</p>` : "";
  return `<div class="card flat ${suppressed ? "struck" : ""}"><h3>Form ${esc(f.id)} ${tags}</h3>${heal}${body}</div>`;
}

export async function openCase(invoiceId, opener) {
  closeDrawer.opener = opener || document.activeElement;
  const d = $("#drawer");
  d.hidden = false; $("#drawerBackdrop").hidden = false;
  d.innerHTML = skeleton(6);
  try {
    const [c, catalog] = await Promise.all([api.get(`/api/results/${invoiceId}`), api.get("/api/codes")]);
    state.codes = catalog;
    const inv = c.invoice, ref = c.reference, b = c.booking;
    const diffRows = c.diffs.map((x) => `<p class="diff small"><b>${esc(x.field)}</b>: invoice <span class="mono">${esc(x.invoice)}</span> vs registered <span class="mono">${esc(x.registered)}</span></p>`).join("");
    const checks = c.checks.map((k) => `<div class="check"><div class="st ${k.passed ? "pass" : "fail"}">${k.passed ? "PASS" : "FAIL"}<br><span class="muted">${esc(k.severity)}</span></div>
      <div><b>${esc(k.name)}</b> <span class="chip sev-${esc(k.severity)}">${esc(k.code)}</span><div class="small muted">${esc(k.detail)}</div></div></div>`).join("");
    const alts = (c.alternatives || []).length ? `<h3>Nearest alternatives</h3><ul class="small">` + c.alternatives.map((a) =>
      `<li><b>${esc(a.name)}</b> (${esc(a.class_name)}) ${esc(a.days)} ${esc(a.time)}, ${a.seats_left} seat(s) left. ${a.caveat ? esc(a.caveat) : "Same class, exact slot."}</li>`).join("") + "</ul>" : "";
    const rows = c.proposed_rows.length ? `<h3>Proposed class_schedule_bookings rows (${c.proposed_rows.length})</h3>
      <div class="scroll tall"><table><thead><tr><th>date</th><th>start</th><th>end</th><th>batch</th><th>booking</th><th>type</th></tr></thead><tbody>` +
      c.proposed_rows.map((r) => `<tr><td>${esc(r.class_date)}</td><td>${esc(r.start_time)}</td><td>${esc(r.end_time)}</td><td>${esc(r.classbatch_id)}</td><td>${r.bookingrequest_id ?? "new"}</td><td>${esc(r.booking_type)}</td></tr>`).join("") + "</tbody></table></div>" : "";
    const msgs = c.messages.length ? c.messages.map((m) => `<div class="msg"><div class="row between"><b>${esc(m.channel)} to ${esc(m.recipient_label)}</b>${srcBadge(m.source)}</div><p class="small" style="white-space:pre-wrap">${esc(m.body)}</p></div>`).join("") :
      '<p class="muted small">No messages generated yet. Open the Messages page to generate them.</p>';
    d.innerHTML = `
      <div class="row between"><h2>Invoice ${esc(inv.invoice_number)}</h2><button class="btn" id="drawerClose">Close</button></div>
      <div class="row">${decisionBadge(c.decision)} <span class="small">Owner: <b>${esc(c.display_owner)}</b></span> <span class="small">SLA: <b>${esc(c.sla.state)}</b>${c.sla.hours_open != null ? " (" + hrs(c.sla.hours_open) + " open)" : ""}</span></div>
      <div class="field" style="margin-top:.5rem">${steps(c.steps)}</div>
      ${chips(c.reason_codes, catalog)}
      <h3>Recommended action</h3>
      <p><b>${esc(c.recommended_action)}</b></p>
      ${c.sla.escalation ? `<p class="diff small">${esc(c.sla.escalation)}</p>` : ""}
      <div class="row no-print">
        ${c.decision === "AUTO_APPROVE" && !c.approved ? '<button class="btn primary" id="dApprove">Approve (simulated)</button>' : ""}
        ${c.approved ? '<span class="badge">Approved (simulated)</span>' : ""}
        ${c.decision === "FAST_TRACK_PENDING_PARENT" ? '<button class="btn primary" id="dParent">Simulate parent reply: continue same batch</button>' : ""}
      </div>
      <h2 style="margin-top:1rem">1. Record chain</h2>
      <div class="chain">
        <div class="card flat"><h3>Invoice</h3>${kv({"Number": inv.invoice_number, "Status": inv.payment_status, "Type": inv.payment_type, "Amount": inr(inv.amount),
      "Discount": inr(inv.discount_amount), "Net": inr(inv.net_amount), "Gateway": inv.payment_gateway, "Paid at": fmtDt(inv.paid_at), "Payer": parentName(ref),
      "Mobile": inv.mobile, "Email": inv.email})}${diffRows}</div>
        <div class="card flat"><h3>Student record</h3>${ref ? kv({"Student": studentName(ref), "Parent": parentName(ref), "Mobile": ref.registered_mobile_masked,
      "Email": ref.registered_email_masked, "Batch": `${ref.classbatch_name} (${ref.current_classbatch_id})`, "Slot": `${ref.batch_days} ${ref.batch_start_time}`,
      "Seats": `${ref.active_students_count}/${ref.max_batch_size}`, "Standard fee": inr(ref.standard_fee_24_sessions_inr)}) : '<p class="muted small">No active record.</p>'}</div>
        ${c.forms.length ? c.forms.map((f) => formCard(c, f)).join("") : '<div class="card flat"><h3>Teacher form</h3><p class="diff small">No form exists for this invoice.</p></div>'}
        <div class="card flat"><h3>Booking request</h3>${b ? kv({"Id": b.id, "Status": b.request_status, "Batch": b.classbatch_id, "Sessions": b.sessions_count,
      "Allocated": b.batch_allocated, "Created": fmtDt(b.created_at)}) : '<p class="diff small">No booking request.</p>'}</div>
        <div class="card flat"><h3>Schedule rows (${c.schedule_rows.length})</h3>${c.schedule_rows.length ? c.schedule_rows.map((r) => `<p class="small mono">${esc(r.id)}: ${esc(r.class_date)} ${esc(r.start_time)}</p>`).join("") : '<p class="diff small">No schedule rows.</p>'}</div>
      </div>
      <h2>2. Checks</h2>${checks}
      <h2 style="margin-top:1rem">3. Healed actions and next steps</h2>
      ${c.healed_actions.length ? "<ul>" + c.healed_actions.map((x) => `<li class="small">${esc(x)}</li>`).join("") + "</ul>" : '<p class="muted small">Nothing healed.</p>'}
      ${c.next_steps.length ? "<ul>" + c.next_steps.map((x) => `<li class="small">${esc(x)}</li>`).join("") + "</ul>" : ""}
      ${alts}${rows}
      <h2 style="margin-top:1rem">4. Linked messages</h2>${msgs}`;
    $("#drawerClose").onclick = closeDrawer;
    $("#dApprove") && ($("#dApprove").onclick = async () => { try { await api.post(`/api/cases/${invoiceId}/approve`); toast("Approved (simulated)"); await openCase(invoiceId, closeDrawer.opener); onChange(); } catch (e) { showError(e.message); } });
    $("#dParent") && ($("#dParent").onclick = async () => { try { await api.post(`/api/cases/${invoiceId}/parent-reply`); toast("Parent replied; case re-run"); await openCase(invoiceId, closeDrawer.opener); onChange(); } catch (e) { showError(e.message); } });
    $("#drawerClose").focus();
  } catch (e) {
    d.innerHTML = `<div class="row between"><h2>Could not open case</h2><button class="btn" id="drawerClose">Close</button></div><p>${esc(e.message)}</p>`;
    $("#drawerClose").onclick = closeDrawer;
  }
}

$("#drawerBackdrop").addEventListener("click", closeDrawer);
addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#drawer").hidden) closeDrawer(); });
