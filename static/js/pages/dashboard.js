import {api} from "../api.js";
import {esc, $, $$, inr, hrs, fmtDt, table, emptyNoData, decisionBadge, chips, OWNERS} from "../util.js";
import {getResults, state} from "../state.js";
import {openCase, setOnChange} from "../components/drawer.js";
import {toast} from "../ui.js";

let charts = [];
const TEAL = "#147d83", SKY = "#4f9fc1", NAVY = "#173b56", AMBER = "#d8893f";

function chart(id, cfg) {
  const el = document.getElementById(id);
  if (!el || typeof Chart === "undefined") return;
  charts.push(new Chart(el, cfg));
}
const dataTable = (head, rows) => `<details class="small"><summary>Chart data as a table</summary>${table(head, rows, "")}</details>`;

export async function render(root) {
  charts.forEach((c) => c.destroy()); charts = [];
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  const m = res.metrics, cases = res.cases, thr = res.settings.stuck_threshold_hours, catalog = state.codes;
  const unsched = cases.filter((c) => ["Paid", "Partially_Paid"].includes(c.invoice.payment_status) && !c.schedule_rows.length);
  const noForm = cases.filter((c) => ["Paid", "Partially_Paid"].includes(c.invoice.payment_status) && !c.forms.some((f) => f.source === "teacher") && (c.sla.hours_since_payment || 0) > thr).length;
  const dc = m.decision_counts, hs = m.hours_saved, A = res.settings.assumptions;

  root.innerHTML = `
    <div class="row between"><div><h1>Morning dashboard</h1><p class="muted">Head of Operations view. As of ${esc(fmtDt(res.as_of))} IST. Stuck means older than ${thr} hours.</p></div>
      <button class="btn no-print" id="printBtn">Print (black and white)</button></div>
    <div class="kpis">
      <div class="kpi"><div class="l">Paid but unscheduled</div><div class="v">${inr(m.paid_unscheduled_value_inr)}</div><div class="n">${unsched.length} renewals, ${m.fully_completed_end_to_end} of ${m.total_invoices} complete</div></div>
      <div class="kpi"><div class="l">Paid, no form over ${thr}h</div><div class="v">${noForm}</div><div class="n">${m.raw_paid_without_valid_form} by plain join, ${m.paid_without_form_after_healing} after healing</div></div>
      <div class="kpi"><div class="l">Forms pending over ${thr}h</div><div class="v">${m.forms_pending_over_threshold}</div><div class="n">oldest ${hrs(m.oldest_pending_form_hours)}; ${m.approval_throughput.approved} of ${m.approval_throughput.total} approved</div></div>
      <div class="kpi"><div class="l">Bookings unscheduled over ${thr}h</div><div class="v">${m.bookings_unscheduled_over_threshold}</div><div class="n">oldest ${hrs(m.oldest_unscheduled_booking_hours)}</div></div>
      <div class="kpi"><div class="l">Touchless rate</div><div class="v">${Math.round(m.touchless_rate_percent)}%</div><div class="n">${dc.AUTO_APPROVE} of ${m.total_invoices}; +${dc.FAST_TRACK_PENDING_PARENT} need a parent tap</div></div>
      <div class="kpi"><div class="l">Hours saved per week (model)</div><div class="v">${hs.ops_hours_saved}</div><div class="n">Ops, plus ${hs.teacher_hours_saved}h teacher. Assumptions.</div></div>
    </div>

    <div class="card"><div class="row between"><h2>Morning brief</h2><div class="row no-print"><span id="briefSrc"></span><button class="btn small" id="briefBtn">Regenerate</button></div></div><ol id="brief" class="small"><li class="muted">Loading...</li></ol></div>

    <div class="grid2">
      <div class="card"><h2>Funnel: today versus with the engine</h2><div class="chartbox"><canvas id="cFunnel" role="img" aria-label="Funnel bar chart comparing raw counts and engine counts per stage"></canvas></div>
        ${dataTable(["Stage", "Today", "With engine"], m.funnel.labels.map((l, i) => [esc(l), m.funnel.raw[i], m.funnel.engine[i]]))}
        <p class="small muted">With the engine: "Approved" counts AUTO_APPROVE plus already complete. Booking requests and scheduled rows follow from approval.</p></div>
      <div class="card"><h2>Ageing by stage</h2><div class="chartbox"><canvas id="cAge" role="img" aria-label="Stacked bar chart of items by age bucket and stage"></canvas></div>
        ${dataTable(["Bucket", "No form", "Form pending", "Booking unscheduled"], m.ageing.buckets.map((b, i) => [esc(b), m.ageing.no_form[i], m.ageing.form_pending[i], m.ageing.booking_unscheduled[i]]))}</div>
    </div>
    <div class="grid2">
      <div class="card"><h2>Exceptions by reason code</h2><div class="chartbox"><canvas id="cPareto" role="img" aria-label="Horizontal bar chart of reason code counts"></canvas></div>
        ${dataTable(["Reason code", "Count"], m.pareto.map((p) => [esc(p.code), p.count]))}</div>
      <div class="card"><h2>Owner workload</h2>
        ${m.owner_workload.length ? '<div class="grid3">' + m.owner_workload.map((w) => `<div class="card flat"><b>${esc(OWNERS[w.owner] || w.owner)}</b><div class="v" style="font-size:1.4rem;font-weight:800">${w.open} open</div>
          <div class="small muted">Oldest ${hrs(w.oldest_hours)}</div><a class="small" href="#/exceptions?owner=${esc(w.owner)}">Open queue</a></div>`).join("") + "</div>" : '<p class="muted">No open exceptions.</p>'}</div>
    </div>

    <div class="card"><h2>Needs action now (rupees x hours waiting)</h2>
      ${table(["Invoice", "Decision", "Owner", "Collected", "Waiting", "Reason codes", "Next step"], m.needs_action.map((n) => [
        `<button class="linklike" data-id="${n.invoice_id}">${esc(n.invoice_id)}</button>`, decisionBadge(n.decision), esc(OWNERS[n.owner] || n.owner), inr(n.collected), hrs(n.hours),
        chips(n.reason_codes, catalog), esc(n.action)]))}</div>

    <div class="card"><h2>SLA panel</h2>
      ${table(["Stage", "Target", "Median now", "Breaches", "What a breach is"], m.sla_panel.map((s) => [esc(s.stage), esc(s.target), s.median == null ? "-" : esc(s.median + " " + s.unit), `<b>${s.breaches}</b>`, esc(s.note)]))}
      <p class="small muted">Headline SLA: payment to schedule, target P90 under ${res.settings.schedule_target_hours}h for clean renewals.</p></div>

    <div class="card"><h2>Hours saved calculator (assumptions, not measurements)</h2>
      <div class="fields">
        <div class="field"><label for="h_n">Renewals per week</label><input id="h_n" type="number" value="${A.renewals_per_week}"></div>
        <div class="field"><label for="h_man">Manual Ops minutes per renewal</label><input id="h_man" type="number" step="0.5" value="${A.manual_minutes}"></div>
        <div class="field"><label for="h_form">Teacher form minutes</label><input id="h_form" type="number" step="0.5" value="${A.teacher_form_minutes}"></div>
        <div class="field"><label for="h_ma">Mix: touchless %</label><input id="h_ma" type="number" value="${Math.round(A.mix_auto * 100)}"></div>
        <div class="field"><label for="h_mp">Mix: parent tap %</label><input id="h_mp" type="number" value="${Math.round(A.mix_parent * 100)}"></div>
        <div class="field"><label for="h_me">Mix: exception %</label><input id="h_me" type="number" value="${Math.round(A.mix_exception * 100)}"></div>
        <div class="field"><label for="h_ta">Minutes: touchless</label><input id="h_ta" type="number" step="0.5" value="${A.minutes_auto}"></div>
        <div class="field"><label for="h_tp">Minutes: parent tap</label><input id="h_tp" type="number" step="0.5" value="${A.minutes_parent}"></div>
        <div class="field"><label for="h_te">Minutes: exception</label><input id="h_te" type="number" step="0.5" value="${A.minutes_exception}"></div>
      </div>
      <div id="hOut" class="kpis"></div><p class="small muted" id="hWarn"></p></div>`;

  chart("cFunnel", {type: "bar", data: {labels: m.funnel.labels, datasets: [
    {label: "Today", data: m.funnel.raw, backgroundColor: SKY, borderColor: NAVY, borderWidth: 1},
    {label: "With engine", data: m.funnel.engine, backgroundColor: TEAL, borderColor: NAVY, borderWidth: 1}]},
    options: {maintainAspectRatio: false, scales: {y: {beginAtZero: true, ticks: {precision: 0}}}}});
  chart("cAge", {type: "bar", data: {labels: m.ageing.buckets, datasets: [
    {label: "Paid, no form", data: m.ageing.no_form, backgroundColor: NAVY},
    {label: "Form pending", data: m.ageing.form_pending, backgroundColor: SKY},
    {label: "Booking unscheduled", data: m.ageing.booking_unscheduled, backgroundColor: AMBER}]},
    options: {maintainAspectRatio: false, scales: {x: {stacked: true}, y: {stacked: true, beginAtZero: true, ticks: {precision: 0}}}}});
  chart("cPareto", {type: "bar", data: {labels: m.pareto.map((p) => p.code), datasets: [{label: "Cases", data: m.pareto.map((p) => p.count), backgroundColor: TEAL, borderColor: NAVY, borderWidth: 1}]},
    options: {indexAxis: "y", maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {x: {beginAtZero: true, ticks: {precision: 0}}}}});

  $$("button.linklike[data-id]", root).forEach((b) => b.addEventListener("click", () => openCase(+b.dataset.id, b)));
  setOnChange(() => render(root));
  $("#printBtn").onclick = () => window.print();

  const calc = () => {
    const g = (id) => +$(id).value || 0;
    const n = g("#h_n"), mix = [g("#h_ma"), g("#h_mp"), g("#h_me")], mins = [g("#h_ta"), g("#h_tp"), g("#h_te")];
    const avg = (mix[0] * mins[0] + mix[1] * mins[1] + mix[2] * mins[2]) / 100;
    const base = n * g("#h_man") / 60, target = n * avg / 60, teacher = n * g("#h_form") / 60;
    $("#hOut").innerHTML = [["Ops hours per week today", base.toFixed(1)], ["Ops hours per week with engine", target.toFixed(1)], ["Ops hours saved per week", (base - target).toFixed(1)],
      ["Teacher hours saved per week", teacher.toFixed(1)], ["Average minutes per renewal", avg.toFixed(2)]].map(([l, v]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div></div>`).join("");
    $("#hWarn").textContent = mix[0] + mix[1] + mix[2] === 100 ? "" : "The three mix percentages should add up to 100.";
  };
  ["#h_n", "#h_man", "#h_form", "#h_ma", "#h_mp", "#h_me", "#h_ta", "#h_tp", "#h_te"].forEach((id) => $(id).addEventListener("input", calc));
  calc();

  async function loadBrief() {
    if (!$("#brief")) return;
    $("#brief").innerHTML = '<li class="muted">Loading...</li>';
    const b = await api.post("/api/brief", {});
    if (!$("#brief")) return;
    $("#brief").innerHTML = b.lines.map((l) => `<li>${esc(l)}</li>`).join("");
    $("#briefSrc").innerHTML = `<span class="src ${b.source === "ai" ? "ai" : ""}">${b.source === "ai" ? "AI" : "Template"}</span>`;
  }
  $("#briefBtn").onclick = () => loadBrief().catch((e) => toast(e.message));
  loadBrief().catch(() => { if ($("#brief")) $("#brief").innerHTML = '<li class="muted">Brief unavailable.</li>'; });
}
