import {esc, $, $$, inr, fmtDt, hrs, decisionBadge, chips, steps, table, emptyNoData, DECISIONS, OWNERS, studentName, parentName} from "../util.js";
import {getResults, state} from "../state.js";
import {openCase, setOnChange} from "../components/drawer.js";

const filters = {decision: "", owner: "", code: "", stuck: false, q: "", sort: "hours"};

export async function render(root, query = {}) {
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  if (query.decision) filters.decision = query.decision;
  const catalog = state.codes;
  const codes = [...new Set(res.cases.flatMap((c) => c.reason_codes))].sort();
  root.innerHTML = `
    <h1>Pipeline</h1>
    <p class="muted">Every renewal invoice and where it stands across the four tables. Click a row for the full record chain. As of ${esc(fmtDt(res.as_of))} IST.</p>
    <div class="card"><div class="fields">
      <div class="field"><label for="f_dec">Decision</label><select id="f_dec"><option value="">All</option>${Object.entries(DECISIONS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
      <div class="field"><label for="f_own">Owner</label><select id="f_own"><option value="">All</option>${Object.entries(OWNERS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
      <div class="field"><label for="f_code">Reason code</label><select id="f_code"><option value="">All</option>${codes.map((c) => `<option>${esc(c)}</option>`).join("")}</select></div>
      <div class="field"><label for="f_q">Search</label><input id="f_q" type="search" placeholder="Invoice, student, parent, class"></div>
      <div class="field"><label for="f_sort">Sort by</label><select id="f_sort"><option value="hours">Hours since payment</option><option value="amount">Amount</option><option value="id">Invoice id</option></select></div>
      <div class="field"><label>&nbsp;</label><label class="row" style="margin:0"><input type="checkbox" id="f_stuck"> Stuck over ${res.settings.stuck_threshold_hours}h only</label></div>
    </div></div>
    <div class="card"><div id="count" class="small muted"></div><div id="list"></div></div>`;
  $("#f_dec").value = filters.decision; $("#f_own").value = filters.owner; $("#f_code").value = filters.code;
  $("#f_q").value = filters.q; $("#f_sort").value = filters.sort; $("#f_stuck").checked = filters.stuck;

  function draw() {
    let cs = res.cases.slice();
    const q = filters.q.toLowerCase();
    cs = cs.filter((c) => (!filters.decision || c.decision === filters.decision) && (!filters.owner || c.display_owner === filters.owner) &&
      (!filters.code || c.reason_codes.includes(filters.code)) &&
      (!filters.stuck || Object.values(c.steps).some((s) => s.state === "stuck")) &&
      (!q || [c.invoice.invoice_number, parentName(c.reference), studentName(c.reference), c.reference && c.reference.class_name, c.reference && c.reference.classbatch_name].join(" ").toLowerCase().includes(q)));
    cs.sort((a, b) => filters.sort === "amount" ? b.invoice.net_amount - a.invoice.net_amount : filters.sort === "id" ? a.invoice.id - b.invoice.id : (b.sla.hours_since_payment || 0) - (a.sla.hours_since_payment || 0));
    $("#count").textContent = `${cs.length} of ${res.cases.length} invoices`;
    if (!cs.length) { $("#list").innerHTML = '<div class="empty">No invoices match these filters.</div>'; return; }
    $("#list").innerHTML = table(["Invoice", "Student and parent", "Class and batch", "Paid", "Paid at", "Since payment", "Tracker", "Decision", "Reason codes"],
      cs.map((c) => {
        const ref = c.reference;
        return [`<button class="linklike" data-id="${c.invoice.id}">${esc(c.invoice.id)}</button>`,
          `${esc(studentName(ref))}<div class="small muted">${esc(parentName(ref))}</div>`,
          `${esc(ref ? ref.class_name : "-")}<div class="small muted">${esc(ref ? ref.classbatch_name : "")}</div>`,
          `${inr(c.invoice.net_amount)}<div class="small muted">${esc(c.invoice.payment_status)}</div>`,
          esc(fmtDt(c.invoice.paid_at || c.invoice.created_at)), hrs(c.sla.hours_since_payment), steps(c.steps),
          decisionBadge(c.decision) + (c.approved ? '<div class="small">Approved (simulated)</div>' : ""), chips(c.reason_codes, catalog)];
      }));
    $$("#list tbody tr").forEach((tr) => {
      const btn = $("button", tr);
      tr.classList.add("click");
      tr.addEventListener("click", (e) => { if (e.target.closest(".chip")) return; openCase(+btn.dataset.id, btn); });
    });
  }
  const bind = (id, key, ev = "change", get = (e) => e.target.value) => $(id).addEventListener(ev, (e) => { filters[key] = get(e); draw(); });
  bind("#f_dec", "decision"); bind("#f_own", "owner"); bind("#f_code", "code"); bind("#f_q", "q", "input");
  bind("#f_sort", "sort"); bind("#f_stuck", "stuck", "change", (e) => e.target.checked);
  setOnChange(() => render(root, {}));
  draw();
}
