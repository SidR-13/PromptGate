import type { GenerateResponse, LocaleCheck, PromptSummary, PromptVersion, Run, Verdict } from "./types";

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

export function listPrompts(): Promise<PromptSummary[]> {
  return request<PromptSummary[]>(`/v1/prompts`);
}

export function getPromptHistory(name: string): Promise<PromptVersion[]> {
  return request<PromptVersion[]>(`/v1/prompts/${encodeURIComponent(name)}/history`);
}

export function getLocaleChecks(runId: string): Promise<LocaleCheck[]> {
  return request<LocaleCheck[]>(`/v1/locale-checks/${runId}`);
}

// Verdict is never cached or stored — every call hits POST /v1/evaluate live,
// which reads raw Run/LocaleCheck rows with no pre-aggregated field in between.
export function evaluateRun(runId: string): Promise<Verdict> {
  return request<Verdict>(`/v1/evaluate`, {
    method: "POST",
    body: JSON.stringify({ run_id: runId }),
  });
}

export function generateRun(body: {
  prompt_name: string;
  input: string;
  locale: string;
}): Promise<GenerateResponse> {
  return request<GenerateResponse>("/v1/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Runs the LLM-as-judge for a single run only. Use this from EvalPanel after
// generating one run — avoids overwriting previously correct scores on older
// runs the way the batch endpoint (evaluateJudge) would.
export function evaluateRunJudge(runId: string): Promise<{
  run_id: string;
  prompt_id: string;
  score: number;
  passed: boolean;
  judge_reasoning: string;
}> {
  return request(`/v1/evaluate/run/${runId}`, { method: "POST" });
}

// Runs the LLM-as-judge over all runs for this prompt_id and writes scores.
// Must be called before evaluateRun() — the verdict endpoint only reads
// the score that judge() writes; it does not invoke the judge itself.
export function evaluateJudge(promptId: string): Promise<{
  prompt_id: string;
  runs_evaluated: number;
  mean_score: number;
  passed: boolean;
  results: { run_id: string; score: number; passed: boolean; judge_reasoning: string }[];
}> {
  return request(`/v1/evaluate/${promptId}`, { method: "POST" });
}

// Runs i18n checks on all runs for this prompt_id version.
export function evaluatePromptLocale(promptId: string): Promise<unknown> {
  return request("/v1/evaluate-locale/" + promptId, { method: "POST" });
}
