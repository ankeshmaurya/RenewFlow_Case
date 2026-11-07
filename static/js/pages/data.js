import {api} from "../api.js";
import {esc, $, $$, table, skeleton} from "../util.js";
import {toast, showError, guard} from "../ui.js";

const TABLES = [
  ["invoices", "1_invoices.csv", "Invoices", "invoices.csv"], ["forms", "2_faculty_form_unapproved.csv", "Teacher forms", "faculty_forms.csv"],
  ["bookings", "3_booking_requests.csv", "Booking requests", "booking_requests.csv"], ["schedule", "4_class_schedule_bookings.csv", "Class schedule bookings", "class_schedule_bookings.csv"],
  ["reference", "reference_active_batches_and_students.csv", "Reference: batches and students", "active_batches_and_students.csv"],
];

function toLocalInput(iso) { return (iso || "").slice(0, 16); }
function fromLocalInput(v) { return v ? v + ":00+05:30" : v; }

function previewTable(rows) {
  if (!rows.length) return '<p class="muted small">No rows.</p>';
  const cols = Object.keys(rows[0]);
  return `<div class="scroll tall"><table><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
    rows.map((r) => "<tr>" + cols.map((c) => `<td>${esc(r[c] ?? "")}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>";
}

export async function render(root) {
  const [health, settings, summary] = await Promise.all([api.get("/api/health"), api.get("/api/settings"), api.get("/api/data/summary")]);
  root.innerHTML = `
    <h1>Data and Run</h1>
    <p class="muted">Load the data, set the as-of time and thresholds, then run the reconciliation.</p>
    <div class="card">
      <h2>1. Load data</h2>
      <div class="row">
        <button class="btn primary" id="loadSample">Load sample data</button>
        <button class="btn" id="runBtn" ${summary.loaded ? "" : "disabled"}>Run reconciliation</button>
        <label class="row" style="margin:0"><input type="checkbox" id="runLLM" ${settings.use_llm ? "checked" : ""}> Use Gemini for remarks and messages</label>
      </div>
      <p class="small muted" id="runStatus">${health.gemini_key_present ? "Gemini key found (model " + esc(health.model) + ")." : "No Gemini key found: templates and keyword rules are used. Everything still works."}</p>
      <h3>Or upload the 5 CSV files</h3>
      <div class="fields">${TABLES.map(([k, f, l, displayFile]) => `<div class="field"><label for="up_${k}">${esc(l)} <span class="mono">File: ${esc(displayFile)}</span></label><input type="file" accept=".csv,text/csv" id="up_${k}"></div>`).join("")}</div>
      <button class="btn" id="uploadBtn">Upload and load</button>
    </div>
    <div class="card">
      <h2>2. As-of time and settings</h2>
      <form id="settingsForm" class="fields" onsubmit="return false">
        <div class="field"><label for="s_as_of">As-of date and time (IST)</label><input type="datetime-local" id="s_as_of" value="${esc(toLocalInput(settings.as_of))}"></div>
        <div class="field"><label for="s_stuck">Stuck threshold (hours)</label><input type="number" step="0.5" id="s_stuck" value="${settings.stuck_threshold_hours}"></div>
        <div class="field"><label for="s_form">Form target (hours)</label><input type="number" step="0.5" id="s_form" value="${settings.form_target_hours}"></div>
        <div class="field"><label for="s_appr">Approval target (hours)</label><input type="number" step="0.25" id="s_appr" value="${settings.approval_target_hours}"></div>
        <div class="field"><label for="s_alloc">Allocation target (hours)</label><input type="number" step="0.25" id="s_alloc" value="${settings.allocation_target_hours}"></div>
        <div class="field"><label for="s_sched">Payment-to-schedule target (hours)</label><input type="number" step="0.5" id="s_sched" value="${settings.schedule_target_hours}"></div>
        <div class="field"><label for="s_min">Session length (minutes)</label><input type="number" id="s_min" value="${settings.session_minutes}"></div>
        <div class="field"><label for="s_n">Sessions per renewal</label><input type="number" id="s_n" value="${settings.sessions_default}"></div>
        <div class="field"><label for="s_pol">Partial payment policy</label><select id="s_pol"><option value="HOLD" ${settings.partial_payment_policy === "HOLD" ? "selected" : ""}>Hold and flag</option><option value="PROVISIONAL_PRO_RATA" ${settings.partial_payment_policy === "PROVISIONAL_PRO_RATA" ? "selected" : ""}>Provisional pro-rata sessions</option></select></div>
      </form>
      <div class="row"><button class="btn" id="saveSettings">Save settings</button><button class="btn" id="resetSettings">Reset to defaults</button><span class="small muted" id="settingsMsg">Press Run reconciliation after changing settings.</span></div>
    </div>
    <div class="card"><h2>3. Loaded tables</h2><div id="tables">${summary.loaded ? skeleton(3) : '<p class="muted">Nothing loaded yet.</p>'}</div></div>`;

  async function showTables() {
    const s = await api.get("/api/data/summary");
    const host = $("#tables");
    if (!s.loaded) { host.innerHTML = '<p class="muted">Nothing loaded yet.</p>'; return; }
    $("#runBtn").disabled = false;
    const previews = await Promise.all(TABLES.map(([k]) => api.get(`/api/data/preview/${k}?limit=10`)));
    host.innerHTML = `<p class="small muted">Date range of records: ${esc(s.date_range.from || "-")} to ${esc(s.date_range.to || "-")}</p>
      <div class="grid2">` + TABLES.map(([k, f, l], i) => {
      const info = s.tables[k] || {};
      const nulls = Object.entries(info.null_counts || {}).map(([c, n]) => `${c}: ${n}`).join(", ") || "none";
      return `<div class="card flat"><h3>${esc(l)}</h3>
        <p class="small"><b>${s.counts[k]}</b> rows${info.skipped ? ", " + info.skipped + " skipped" : ""}. Extra columns: ${esc((info.extra_columns || []).join(", ") || "none")}.</p>
        <details><summary class="small">Null counts per column</summary><p class="small mono">${esc(nulls)}</p></details>
        ${previewTable(previews[i].rows)}</div>`;
    }).join("") + "</div>";
  }
  if (summary.loaded) await showTables();

  $("#loadSample").onclick = () => guard(async () => {
    $("#loadSample").disabled = true;
    try { await api.post("/api/data/load-sample"); toast("Sample data loaded and reconciled"); await showTables(); showError(""); }
    finally { $("#loadSample").disabled = false; }
  });
  $("#uploadBtn").onclick = () => guard(async () => {
    const body = {};
    for (const [k] of TABLES) {
      const f = $("#up_" + k).files[0];
      if (!f) throw new Error("Choose a file for every table before uploading.");
      body[k] = await f.text();
    }
    try { await api.post("/api/data/upload", body); toast("Files loaded and reconciled"); await showTables(); showError(""); }
    catch (e) {
      const t = e.detail && e.detail.tables ? Object.entries(e.detail.tables).filter(([, v]) => v.errors && v.errors.length).map(([k, v]) => `${k}: ${v.errors[0]}`).join(" | ") : "";
      throw new Error((e.message || "Upload failed") + (t ? " (" + t + ")" : ""));
    }
  });
  $("#runBtn").onclick = () => guard(async () => {
    $("#runStatus").textContent = "Running...";
    const r = await api.post("/api/reconcile", {use_llm: $("#runLLM").checked});
    const c = r.decision_counts;
    $("#runStatus").textContent = `Done. Auto-approve ${c.AUTO_APPROVE}, waiting on parent ${c.FAST_TRACK_PENDING_PARENT}, flagged ${c.FLAGGED}, blocked ${c.BLOCKED}, complete ${c.ALREADY_COMPLETE}. Remarks read by: ${r.remark_source}.`;
    toast("Reconciliation complete");
  });
  const readSettings = () => ({
    as_of: fromLocalInput($("#s_as_of").value), stuck_threshold_hours: +$("#s_stuck").value, form_target_hours: +$("#s_form").value,
    approval_target_hours: +$("#s_appr").value, allocation_target_hours: +$("#s_alloc").value, schedule_target_hours: +$("#s_sched").value,
    session_minutes: +$("#s_min").value, sessions_default: +$("#s_n").value, partial_payment_policy: $("#s_pol").value, use_llm: $("#runLLM").checked,
  });
  $("#saveSettings").onclick = () => guard(async () => { await api.put("/api/settings", readSettings()); toast("Settings saved. Press Run reconciliation."); });
  $("#resetSettings").onclick = () => guard(async () => { await api.post("/api/settings/reset"); toast("Defaults restored"); await render(root); });
}
