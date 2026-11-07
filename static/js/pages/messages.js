import {api} from "../api.js";
import {esc, $, $$, emptyNoData, srcBadge, messageRecipient} from "../util.js";
import {getResults} from "../state.js";
import {toast, guard} from "../ui.js";

const f = {channel: "", role: "", language: "", status: ""};
const LANGS = ["English", "Hindi", "Hinglish"];

async function copy(text) {
  try { await navigator.clipboard.writeText(text); } catch (e) {
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  toast("Copied");
}

export async function render(root) {
  const res = await getResults();
  if (!res) { root.innerHTML = emptyNoData(); return; }
  let msgs = await api.get("/api/messages");
  if (!msgs.length) msgs = await api.post("/api/messages/generate", {});
  const roles = [...new Set(msgs.map((m) => m.recipient_role))];
  root.innerHTML = `
    <h1>Messages</h1>
    <p class="muted">Drafted WhatsApp and Slack messages. Nothing is sent from here: Mark sent only records a simulated send. Templates always work; Gemini rewrites them when a key is set, and every number, date and id is checked before an AI version is accepted.</p>
    <p class="diff small">Privacy: only masked names and the minimum facts needed (ids, amounts, dates, codes) are sent to Gemini, never full records. Real names are merged at send time by the messaging workflow.</p>
    <div class="card"><div class="fields">
      <div class="field"><label for="m_ch">Channel</label><select id="m_ch"><option value="">All</option><option>whatsapp</option><option>slack</option></select></div>
      <div class="field"><label for="m_ro">Recipient</label><select id="m_ro"><option value="">All</option>${roles.map((r) => `<option>${esc(r)}</option>`).join("")}</select></div>
      <div class="field"><label for="m_st">Status</label><select id="m_st"><option value="">All</option><option>draft</option><option>approved</option><option>sent-simulated</option></select></div>
      <div class="field"><label for="m_lg">Language to generate</label><select id="m_lg">${LANGS.map((l) => `<option>${l}</option>`).join("")}</select></div>
      <div class="field"><label>&nbsp;</label><button class="btn primary" id="m_gen">Regenerate all drafts</button></div>
    </div><label class="row" style="margin:0"><input type="checkbox" id="m_ai" ${res.settings.use_llm ? "checked" : ""}> Use Gemini ${res.llm.key_present ? "" : "(no key found, templates will be used)"}</label>
    <p class="small muted" id="m_count"></p></div>
    <div id="mlist"></div>`;
  $("#m_ch").value = f.channel; $("#m_ro").value = f.role; $("#m_st").value = f.status;

  function draw() {
    const list = msgs.filter((m) => (!f.channel || m.channel === f.channel) && (!f.role || m.recipient_role === f.role) && (!f.status || m.status === f.status));
    $("#m_count").textContent = `${list.length} of ${msgs.length} messages`;
    $("#mlist").innerHTML = list.length ? list.map((m) => `<div class="msg" data-id="${esc(m.id)}">
      <div class="row between"><span><b>Invoice ${esc(m.invoice_id)}</b> | ${esc(m.kind.replaceAll("_", " "))} | ${esc(m.channel)} to ${esc(messageRecipient(m))} ${srcBadge(m.source)} <span class="tag">${esc(m.status)}</span> <span class="small muted">${esc(m.language)}</span></span></div>
      ${m.fallback_note ? `<p class="small muted">${esc(m.fallback_note)}</p>` : ""}
      <label class="sr" for="b_${esc(m.id)}">Message text</label><textarea id="b_${esc(m.id)}" data-edit="${esc(m.id)}">${esc(m.body)}</textarea>
      <div class="small muted">${m.body.length} characters. Call to action: ${esc(m.cta || "none")}</div>
      <div class="row no-print" style="margin-top:.4rem"><button class="btn small" data-save="${esc(m.id)}">Save edit</button>
        <button class="btn small" data-regen="${esc(m.id)}">Regenerate with AI</button>
        <button class="btn small" data-copy="${esc(m.id)}">Copy</button>
        <button class="btn small" data-approve="${esc(m.id)}">Mark approved</button>
        <button class="btn small" data-sent="${esc(m.id)}">Mark sent (simulated)</button></div></div>`).join("") : '<div class="empty">No messages match.</div>';
    const by = (id) => msgs.find((m) => m.id === id);
    const status = (id, s) => guard(async () => { Object.assign(by(id), await api.post(`/api/messages/${encodeURIComponent(id)}/status`, {status: s})); toast("Status: " + s); draw(); });
    $$("[data-save]").forEach((b) => b.onclick = () => guard(async () => { const id = b.dataset.save; Object.assign(by(id), await api.put(`/api/messages/${encodeURIComponent(id)}`, {body: $(`#b_${CSS.escape(id)}`).value})); toast("Saved"); draw(); }));
    $$("[data-regen]").forEach((b) => b.onclick = () => guard(async () => { const id = b.dataset.regen; b.disabled = true;
      Object.assign(by(id), await api.post(`/api/messages/${encodeURIComponent(id)}/regenerate`, {language: $("#m_lg").value, use_llm: $("#m_ai").checked})); toast("Regenerated"); draw(); }));
    $$("[data-copy]").forEach((b) => b.onclick = () => copy($(`#b_${CSS.escape(b.dataset.copy)}`).value));
    $$("[data-approve]").forEach((b) => b.onclick = () => status(b.dataset.approve, "approved"));
    $$("[data-sent]").forEach((b) => b.onclick = () => status(b.dataset.sent, "sent-simulated"));
  }
  $("#m_ch").onchange = (e) => { f.channel = e.target.value; draw(); };
  $("#m_ro").onchange = (e) => { f.role = e.target.value; draw(); };
  $("#m_st").onchange = (e) => { f.status = e.target.value; draw(); };
  $("#m_gen").onclick = () => guard(async () => {
    $("#m_gen").disabled = true;
    msgs = await api.post("/api/messages/generate", {language: $("#m_lg").value, use_llm: $("#m_ai").checked});
    toast("Drafts regenerated"); $("#m_gen").disabled = false; draw();
  });
  draw();
}
