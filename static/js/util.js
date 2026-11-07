export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
export const inr = (n) => (n == null ? "-" : "\u20B9" + Number(n).toLocaleString("en-IN", {maximumFractionDigits: 0}));
export const hrs = (h) => (h == null ? "-" : h >= 48 ? (h / 24).toFixed(1) + "d" : Number(h).toFixed(1) + "h");
export function fmtDt(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return esc(iso);
  return d.toLocaleString("en-IN", {timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false});
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export const DECISIONS = {
  AUTO_APPROVE: "Auto-approve", FAST_TRACK_PENDING_PARENT: "Waiting on parent", FLAGGED: "Flagged",
  BLOCKED: "Blocked", ALREADY_COMPLETE: "Already complete",
};
export const OWNERS = {
  NONE: "No owner", PARENT: "Parent", TEACHER: "Teacher", OPS_LEAD: "Ops Lead", FINANCE_OPS: "Finance Ops",
  SCHEDULING_DESK: "Scheduling Desk", DATA_DESK: "Data Desk",
};
const DEMO_STUDENTS = {
  68101: "Aarav Sharma", 68102: "Diya Nair", 68103: "Kabir Verma", 68104: "Ananya Iyer",
  68105: "Reyansh Patel", 68106: "Zoya Khan", 68107: "Vivaan Joshi", 68108: "Sia Malhotra",
  68109: "Aditya Kulkarni", 68110: "Ishaan Gupta", 68111: "Tara Mehta", 68112: "Rohan Mehra",
  68113: "Devika Menon",
};
const DEMO_PARENTS = {
  41021: "Priya Sharma", 41022: "Karan Nair", 41023: "Neha Verma", 41024: "Rishi Iyer",
  41025: "Meera Patel", 41026: "Farhan Khan", 41027: "Pooja Joshi", 41028: "Sanjay Malhotra",
  41029: "Aditi Kulkarni", 41030: "Vikram Gupta", 41031: "Maya Mehta", 41032: "Suresh Mehra",
  41033: "Mary Menon",
};
const DEMO_INVOICES = {
  84901: [68101, 41021], 84902: [68102, 41022], 84903: [68103, 41023], 84904: [68104, 41024],
  84905: [68105, 41025], 84906: [68106, 41026], 84907: [68107, 41027], 84908: [68108, 41028],
  84909: [68109, 41029], 84910: [68110, 41030], 84911: [68111, 41031], 84912: [68112, 41032],
  84913: [68113, 41033],
};
export const studentName = (record) => DEMO_STUDENTS[record?.student_id] || record?.student_name_masked || "-";
export const parentName = (record) => DEMO_PARENTS[record?.user_id] || record?.parent_name_masked || "-";
export const messageRecipient = (message) => {
  const ids = DEMO_INVOICES[message?.invoice_id];
  const student = DEMO_STUDENTS[message?.student_id || ids?.[0]];
  const parent = DEMO_PARENTS[message?.user_id || ids?.[1]];
  return student || parent ? `${parent || "Parent"}${student ? ` (${student})` : ""}` : message?.recipient_label || "-";
};
export const decisionBadge = (d) => `<span class="badge dec-${esc(d)}">${esc(DECISIONS[d] || d)}</span>`;
export const srcBadge = (s) => `<span class="src ${s === "ai" ? "ai" : ""}" title="${s === "ai" ? "Written by Gemini, facts checked" : "Deterministic template"}">${s === "ai" ? "AI" : "Template"}</span>`;

export function chips(codes, catalog) {
  if (!codes || !codes.length) return '<span class="muted small">none</span>';
  return '<div class="chips">' + codes.map((c) => {
    const info = catalog && catalog[c];
    return `<span class="chip sev-${esc(info ? info.severity : "info")}" title="${esc(info ? info.title + ": " + info.meaning : c)}">${esc(c)}</span>`;
  }).join("") + "</div>";
}
export function steps(s) {
  if (!s) return "";
  const names = {invoice: "Invoice", form: "Form", booking: "Booking", schedule: "Schedule"};
  return '<div class="steps">' + Object.keys(names).map((k) => s[k] ? `<span class="step st-${esc(s[k].state)}"><i>${names[k]}</i>${esc(s[k].label)}</span>` : "").join("") + "</div>";
}
export function kv(obj) {
  return '<dl class="kv">' + Object.entries(obj).filter(([, v]) => v !== undefined).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v === null || v === "" ? "-" : esc(v)}</dd>`).join("") + "</dl>";
}
export function table(headers, rows, cls = "rt") {
  return `<div class="scroll"><table class="${cls}"><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>` +
    rows.map((r) => "<tr>" + r.map((c, i) => `<td data-label="${esc(headers[i])}">${c}</td>`).join("") + "</tr>").join("") + "</tbody></table></div>";
}
export function emptyNoData() {
  return `<div class="empty"><h2>No data loaded yet</h2><p>Load the sample data or upload the five CSV files first.</p><a class="btn primary" href="#/data">Go to Data and Run</a></div>`;
}
export function skeleton(n = 4) { return Array.from({length: n}, () => '<div class="skel"></div>').join(""); }
