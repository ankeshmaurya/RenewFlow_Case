async function req(method, url, body) {
  const opts = {method, headers: {}};
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, opts); } catch (e) { throw new Error("Cannot reach the server. Is uvicorn running?"); }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const d = (data && (data.detail ?? data.error)) ?? r.statusText;
    const msg = typeof d === "string" ? d : (d.message || JSON.stringify(d));
    const err = new Error(msg); err.status = r.status; err.detail = d; throw err;
  }
  return data;
}
export const api = {
  get: (u) => req("GET", u), post: (u, b = {}) => req("POST", u, b), put: (u, b) => req("PUT", u, b),
};
