import {api} from "../api.js";
import {esc, table, hrs, emptyNoData, decisionBadge, chips} from "../util.js";
import {getResults, state} from "../state.js";
import {openCase} from "../components/drawer.js";
import {$$} from "../util.js";

export async function render(root) {
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  const [st, sh] = await Promise.all([api.get("/api/selftest"), api.get("/api/shadow")]);
  root.innerHTML = `
    <h1>Shadow mode and self-test</h1>
    <div class="card"><h2>Self-test against the golden answer</h2>
      <p><b>${st.matched} of ${st.total}</b> invoices match. <b>${st.metrics_matched} of ${st.metrics_total}</b> metrics match. <b>${st.forms_matched} of ${st.forms_total}</b> form checks match.
        Result: <b>${st.passed ? "PASS" : "FAIL"}</b>. The self-test always runs deterministically with default settings, so Gemini cannot change it.</p>
      ${table(["Invoice", "Expected decision", "Actual decision", "Expected codes", "Actual codes", "Owner", "Result"], st.invoices.map((i) => [
        `<button class="linklike" data-id="${esc(i.invoice_id)}">${esc(i.invoice_id)}</button>`, decisionBadge(i.expected.decision), i.actual ? decisionBadge(i.actual.decision) : "-",
        chips(i.expected.expectedReasonCodes, state.codes), chips(i.actual ? i.actual.reason_codes : [], state.codes), esc(i.expected.owner),
        i.match ? '<b class="pass">MATCH</b>' : `<b class="fail">MISMATCH</b> <span class="small">${esc(i.problems.join("; "))}</span>`]))}
      <details><summary>Metric checks and form checks</summary>
        ${table(["Metric", "Expected", "Actual", "Result"], st.metrics.map((m) => [esc(m.metric), esc(JSON.stringify(m.expected)), esc(JSON.stringify(m.actual)), m.match ? "MATCH" : "MISMATCH"]))}
        ${table(["Check", "Result"], st.forms.map((f) => [esc(f.check), f.match ? "MATCH" : "MISMATCH"]))}</details></div>

    <div class="card"><h2>Shadow comparison: engine versus the human approvers</h2>
      <p>Agreement on already-approved forms: <b>${sh.agreed} of ${sh.approved_total} (${sh.agreement_rate}%)</b>. Gate to Assist mode needs ${sh.gate.required_agreement}% agreement and zero wrong schedules.
        Gate status: <b>${sh.gate.open ? "OPEN" : "NOT YET"}</b>. ${esc(sh.gate.reason)}</p>
      ${table(["Form", "Invoice", "Approved by", "Human took", "Engine says", "Agree", "Stalled after approval", "Note"], sh.approved.map((a) => [
        esc(a.form_id), `<button class="linklike" data-id="${a.invoice_id}">${a.invoice_id}</button>`, esc(a.approved_by), hrs(a.human_hours), decisionBadge(a.engine_decision),
        a.agree ? "<b>Yes</b>" : '<b class="fail">No</b>', a.stalled_downstream ? `Yes (${esc(a.booking_status)})` : "No", esc(a.note)]))}</div>

    <div class="card"><h2>Forms still waiting for a human</h2>
      <p>The engine would remove <b>${sh.removed_wait_hours} waiting hours</b> (forms it approves or drops as duplicates) and instantly triage another <b>${sh.triaged_wait_hours} hours</b> of waiting to the right owner.</p>
      ${table(["Form", "Invoice", "Has waited", "Engine needs", "Engine decision", "Waiting removed"], sh.pending.map((p) => [
        esc(p.form_id), `<button class="linklike" data-id="${p.invoice_id}">${p.invoice_id}</button>`, hrs(p.waited_hours), "about " + p.engine_seconds + " second", decisionBadge(p.engine_decision),
        p.waiting_removed ? (p.suppressed_duplicate ? "Yes (duplicate dropped)" : "Yes") : "No, routed to owner"]))}</div>`;
  $$("button.linklike[data-id]", root).forEach((b) => b.addEventListener("click", () => openCase(+b.dataset.id, b)));
}
