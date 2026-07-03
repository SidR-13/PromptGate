export interface Run {
  id: string;
  prompt_id: string;
  prompt_name: string;
  version: number;
  input: string;
  output: string;
  locale: string;
  score: number | null;
  judge_reasoning: string | null;
  blocked: boolean;
  block_reason: string | null;
  created_at: string;
}

export interface PromptSummary {
  name: string;
  latest_version: number;
}

export interface LocaleCheck {
  id: string;
  run_id: string;
  locale: string;
  check_type: string;
  passed: boolean;
  details: string;
  created_at: string;
}

export interface LocaleResultItem {
  check_type: string;
  passed: boolean;
  details: string;
}

export interface Verdict {
  run_id: string;
  eval_score: number | null;
  blocked: boolean;
  block_reason: string | null;
  locale_results: LocaleResultItem[];
  can_ship: boolean;
  reasons: string[];
}

export interface PromptVersion {
  id: string;
  name: string;
  version: number;
  template: string;
  created_at: string;
}

export interface GenerateResponse {
  output: string;
  locale: string;
  run_id: string | null;
  prompt_id: string | null;
  version: number | null;
  blocked: boolean;
  block_reason: string | null;
}
