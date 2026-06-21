import type { Run, Verdict } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${options?.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export function listRuns(skip = 0, limit = 50): Promise<Run[]> {
  return request<Run[]>(`/v1/runs?skip=${skip}&limit=${limit}`);
}

export function getRun(id: string): Promise<Run> {
  return request<Run>(`/v1/runs/${id}`);
}

// Verdict is never cached or stored — every call hits POST /v1/evaluate live,
// which itself reads raw Run/LocaleCheck rows with no pre-aggregated field
// in between. Keeping the frontend on the same "no shortcuts" pattern as
// the rest of this project.
export function evaluateRun(runId: string): Promise<Verdict> {
  return request<Verdict>(`/v1/evaluate`, {
    method: "POST",
    body: JSON.stringify({ run_id: runId }),
  });
}
