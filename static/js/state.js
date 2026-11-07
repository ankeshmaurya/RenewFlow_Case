import {api} from "./api.js";
export const state = {codes: null};
export async function loadCodes() { if (!state.codes) state.codes = await api.get("/api/codes"); return state.codes; }
export async function getResults() {
  try { return await api.get("/api/results"); } catch (e) { if (e.status === 409) return null; throw e; }
}
export async function getMessages() {
  let msgs = await api.get("/api/messages");
  if (!msgs.length) msgs = await api.post("/api/messages/generate", {});
  return msgs;
}
