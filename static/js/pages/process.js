import {api} from "../api.js";
import {esc, table, hrs, inr} from "../util.js";
import {getResults, state} from "../state.js";

const AS_IS = [
  ["1. Teacher pitches, parent pays: invoice created", "F4 form filed on unpaid payment. F5 installment treated as full. F6 untracked discount. F7 payer is not the registered parent."],
  ["2. Teacher re-types the renewal form", "F1 teacher never files (orphan). F2 invoice id typo. F3 duplicate submit."],
  ["3. Ops checks and approves by hand", "F8 no queue order or owner. F9 approval without batch or capacity check. F10 weekend dependence on individuals."],
  ["4. Booking request waits for allocation", "F11 black hole: valid booking sits unallocated for days."],
  ["5. Batch, days and time chosen", "F12 false 'batch full' for a student who already holds the seat. F13 batch change with no available batch."],
  ["6. Schedule rows created", "F14 fewer sessions scheduled than bought."],
];

export async function render(root) {
  const res = await getResults();
  const m = res ? res.metrics : null;
  const catalog = state.codes;
  const rows = Object.entries(catalog).filter(([, v]) => v.channel !== "none").map(([k, v]) => [`<span class="mono">${esc(k)}</span>`, esc(v.owner), esc(v.channel), v.sla_hours ? v.sla_hours + "h" : "FYI", esc(v.fix)]);
  const b = (v, f = (x) => x) => (m ? f(v) : "-");
  root.innerHTML = `
    <h1>Process: as-is versus to-be</h1>
    <p class="muted">Why the teacher form is the step to question, and how a clean renewal flows with no human touch.</p>
    <div class="grid2">
      <div class="card"><h2>As-is: four tables, three manual handoffs</h2><div class="flow">
        ${AS_IS.map(([s, f], i) => `<div class="s ${i === 1 || i === 2 ? "bad" : ""}"><b>${esc(s)}</b><div class="small muted">${esc(f)}</div></div>`).join("")}
        <div class="s bad"><b>Across all steps: F15</b><div class="small muted">The parent sees no status until a class does not happen. F16 gateway and currency friction.</div></div></div></div>
      <div class="card"><h2>To-be: payment is the trigger</h2><div class="flow">
        <div class="s"><b>Payment webhook</b> (Razorpay or Stripe), idempotent on gateway payment id</div>
        <div class="s"><b>Renewal case built</b> from invoice plus student record. The form is no longer needed for data the invoice already holds.</div>
        <div class="s"><b>Rules engine</b>: money, identity, batch, linkage</div></div>
        <div class="lane g"><b>Green: same batch, clean.</b> Auto booking and schedule rows. WhatsApp confirmation to parent, FYI to teacher. Zero human touch.</div>
        <div class="lane o"><b>Orange: parent input.</b> No form, or batch change with options. One-tap WhatsApp. Escalates to an Ops agent after 4 hours.</div>
        <div class="lane r"><b>Red: human decision.</b> Discount, partial payment, no available batch. Named owner, timer, drafted message.</div>
        <div class="lane b"><b>Blocked: payment not confirmed.</b> Re-poll the gateway, tell the parent not to pay again.</div>
        <p class="small muted">A 15-minute sweeper job reconciles against the gateway to catch missed webhooks.</p></div>
    </div>
    <div class="card"><h2>Exception routing matrix</h2>${table(["Reason code", "Owner", "Channel", "SLA", "Fix"], rows)}</div>
    <div class="card"><h2>SLA definitions and sample baselines</h2>
      <ul class="small">
        <li><b>Payment-to-Schedule Turnaround (headline):</b> payment captured to renewed sessions existing. Target: P90 under 4h for clean renewals, under 24h for every exception. Baseline: ${m ? (m.median_payment_to_schedule_hours ?? "-") + "h for the only completed case" : "-"}.</li>
        <li><b>Orphaned Invoice Rate:</b> paid invoices with no valid form. Baseline: ${b(m && m.raw_paid_without_valid_form)} of ${b(m && m.payment_confirmed)} by plain join, ${b(m && m.paid_without_form_after_healing)} after healing.</li>
        <li><b>Form backlog over threshold:</b> ${b(m && m.forms_pending_over_threshold)} of ${b(m && m.approval_throughput.total)} forms, oldest ${b(m && m.oldest_pending_form_hours, hrs)}.</li>
        <li><b>Approved-but-stalled:</b> ${b(m && m.approved_but_stalled.stalled)} of ${b(m && m.approved_but_stalled.approved)} human approvals stalled downstream.</li>
        <li><b>False batch-full:</b> ${b(m && m.false_batch_full_count)}. <b>Duplicate forms:</b> ${b(m && m.duplicate_form_count)}. <b>Id typos healed:</b> ${b(m && m.typo_count)}. <b>Payer mismatch:</b> ${b(m && m.payer_mismatch_count)}. <b>Unapproved discounts:</b> ${b(m && m.discount_unapproved_count)}.</li>
        <li><b>Paid-unscheduled value:</b> ${b(m && m.paid_unscheduled_value_inr, inr)}.</li>
        <li><b>Touchless rate:</b> ${b(m && m.touchless_rate_percent)}% today with rule fixes alone. Target 60% or more, then 70% once the form is removed.</li>
        <li><b>Class Gap Days:</b> days between the last session of the old term and the first of the new. Needs session history, so it is defined here and instrumented from day one. Target zero.</li>
      </ul></div>
    <div class="grid2">
      <div class="card"><h2>Where AI is used (Gemini)</h2><ul class="small"><li>Reads teacher remarks and extracts intent (discount, batch change, third-party payer, payment trouble, resubmission), then cross-checks against the form fields.</li>
        <li>Drafts WhatsApp and Slack messages in English, Hindi or Hinglish. Numbers, dates and ids are checked before an AI version is accepted.</li><li>Writes the morning brief.</li></ul></div>
      <div class="card"><h2>What stays deterministic (rules)</h2><ul class="small"><li>Payment status, amounts, discounts, fees.</li><li>Id linkage, typo healing, duplicate suppression.</li><li>Seat and capacity logic, batch matching.</li><li>SLA clocks, decisions, owners.</li></ul>
        <p class="small muted">If Gemini is unavailable, everything still runs from templates and keyword rules.</p></div>
    </div>`;
}
