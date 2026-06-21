export interface Run {
  id: string;
  prompt_id: string;
  input: string;
  output: string;
  locale: string;
  score: number | null;
  judge_reasoning: string | null;
  blocked: boolean;
  block_reason: string | null;
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
