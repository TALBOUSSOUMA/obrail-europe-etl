// Centralized API client: a single fetch function with uniform error
// handling, reused by every page. The base URL comes from a Vite
// environment variable (VITE_API_URL), with a local fallback for
// development - this is what lets the same build run as-is in a
// Docker container (Step 3) without any code change.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

async function request(path, options) {
  const resp = await fetch(`${API_URL}${path}`, options);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message = body.detail || `Erreur ${resp.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return resp.json();
}

export function getDessertes(params = {}) {
  const query = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null))
  );
  return request(`/dessertes?${query.toString()}`);
}

export function getPays() {
  return request("/pays");
}

export function getOperateurs() {
  return request("/operateurs");
}

export function getGares() {
  return request("/gares");
}

export function getTypesTrain() {
  return request("/types-train");
}

export function getStatsOperateurs() {
  return request("/stats/operateurs");
}

export function getStatsPays() {
  return request("/stats/pays");
}

export function getQualite(limit = 10) {
  return request(`/qualite?limit=${limit}`);
}

export function getHealth() {
  return request("/health");
}

export function postPredict(payload) {
  return request("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export { API_URL };
