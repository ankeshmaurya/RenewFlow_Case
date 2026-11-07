import {$} from "./util.js";
export function showError(msg) { const b = $("#banner"); b.textContent = msg; b.hidden = !msg; }
export function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 2600);
}
export function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, qs] = raw.split("?");
  return {path: path || "dashboard", query: Object.fromEntries(new URLSearchParams(qs || ""))};
}
export async function guard(fn) {
  try { return await fn(); } catch (e) { showError(e.message || String(e)); return null; }
}
