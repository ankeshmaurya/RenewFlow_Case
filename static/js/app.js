import {$, esc} from "./util.js";
import {showError, parseHash} from "./ui.js";
import * as data from "./pages/data.js";
import * as pipeline from "./pages/pipeline.js";
import * as dashboard from "./pages/dashboard.js";
import * as approved from "./pages/approved.js";
import * as exceptions from "./pages/exceptions.js";
import * as messages from "./pages/messages.js";
import * as processPage from "./pages/process.js";
import * as shadow from "./pages/shadow.js";
import {loadCodes} from "./state.js";

const ROUTES = [
  ["dashboard", "Dashboard", dashboard], ["pipeline", "Pipeline", pipeline], ["auto-approved", "Auto-Approved", approved],
  ["exceptions", "Exceptions", exceptions], ["messages", "Messages", messages], ["process", "Process", processPage],
  ["shadow", "Shadow and Self-Test", shadow], ["data", "Data and Run", data],
];

function buildNav(active) {
  $("#nav").innerHTML = '<div class="logo">RenewFlow<span>Bambinos.live Operations</span></div>' +
    ROUTES.map(([id, label]) => `<a href="#/${id}" ${id === active ? 'aria-current="page"' : ""}>${esc(label)}</a>`).join("");
}

async function render() {
  const {path, query} = parseHash();
  const route = ROUTES.find((r) => r[0] === path) || ROUTES[0];
  buildNav(route[0]);
  $("#nav").classList.remove("open"); $("#navToggle").setAttribute("aria-expanded", "false");
  showError("");
  const app = $("#app");
  app.innerHTML = '<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  try {
    await loadCodes();
    await route[2].render(app, query);
  } catch (e) {
    app.innerHTML = '<div class="empty">This page could not be shown.</div>';
    showError(e.message || String(e));
  }
  $("#main").focus({preventScroll: true});
}

$("#navToggle").addEventListener("click", () => {
  const open = $("#nav").classList.toggle("open");
  $("#navToggle").setAttribute("aria-expanded", String(open));
});
addEventListener("hashchange", render);
render();
