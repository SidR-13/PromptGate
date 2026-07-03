import { useState } from "react";
import type { PromptSummary } from "../api/types";
import { generateRun, evaluateRun, evaluateRunJudge, evaluatePromptLocale } from "../api/client";
import { ScoreBar } from "./ScoreBar";

const LOCALES = ["en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"] as const;

const STEPS = [
  { n: 1, label: "Generate" },
  { n: 2, label: "Evaluate" },
  { n: 3, label: "Locale checks" },
];

const inputStyle: React.CSSProperties = {
  padding: "0.375rem 0.5rem",
  borderRadius: "0.375rem",
  border: "1px solid var(--color-border)",
  background: "var(--color-surface)",
  color: "var(--color-text-primary)",
  fontSize: "0.875rem",
  width: "100%",
  boxSizing: "border-box",
};

interface Props {
  prompts: PromptSummary[];
  onRunComplete: () => void;
}

export function EvalPanel({ prompts, onRunComplete }: Props) {
  const [open, setOpen] = useState(false);
  const [promptName, setPromptName] = useState("");
  const [input, setInput] = useState("");
  const [locale, setLocale] = useState("en-US");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0); // 0=idle, 1=generate, 2=evaluate, 3=locale
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ label: string; score: number | null } | null>(null);

  function toggle() {
    if (loading) return; // can't close while a run is in progress
    setOpen((o) => !o);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    setStep(1);

    try {
      // Step 1: generate run
      const gen = await generateRun({ prompt_name: promptName, input, locale });
      if (!gen.run_id || !gen.prompt_id) {
        throw new Error("Generate succeeded but returned no run_id or prompt_id");
      }

      // Step 2: run the judge for this run only — writes score to the runs table.
      // POST /v1/evaluate/run/{run_id} targets one run, so it never overwrites
      // previously correct scores on other runs for the same prompt.
      setStep(2);
      const judgeResult = await evaluateRunJudge(gen.run_id).catch((err) => {
        console.error("[EvalPanel] judge step failed:", err);
        throw new Error(`Evaluate failed: ${err instanceof Error ? err.message : String(err)}`);
      });
      console.log(
        `[EvalPanel] judge result for run ${gen.run_id}: score=${judgeResult.score}, passed=${judgeResult.passed}`
      );

      // Step 3: i18n checks for all runs on this prompt version
      setStep(3);
      await evaluatePromptLocale(gen.prompt_id).catch((err) => {
        console.error("[EvalPanel] locale check step failed:", err);
        throw new Error(`Locale checks failed: ${err instanceof Error ? err.message : String(err)}`);
      });

      // Final verdict — both judge score and locale checks now written;
      // POST /v1/evaluate reads them as raw rows (no cached field).
      const verdict = await evaluateRun(gen.run_id).catch((err) => {
        console.error("[EvalPanel] verdict step failed:", err);
        throw new Error(`Verdict failed: ${err instanceof Error ? err.message : String(err)}`);
      });
      console.log(`[EvalPanel] final verdict for run ${gen.run_id}:`, verdict);

      // Step 4: refresh the runs table in the parent
      onRunComplete();

      // Step 5: show success summary, collapse panel, scroll new row into view
      setSuccess({
        label: verdict.can_ship ? "Ships" : "Blocked",
        score: verdict.eval_score,
      });
      setStep(0);
      setOpen(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStep(0);
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = !loading && promptName !== "" && input.trim() !== "";

  return (
    <div
      style={{
        border: "1px solid var(--color-border)",
        borderLeft: "2px solid var(--color-border-info)",
        borderRadius: "0.5rem",
        background: "var(--color-surface)",
        marginBottom: "1rem",
      }}
    >
      {/* Toggle header */}
      <button
        type="button"
        onClick={toggle}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.75rem 1rem",
          background: "none",
          border: "none",
          cursor: loading ? "not-allowed" : "pointer",
          fontSize: "0.875rem",
          fontWeight: 600,
          color: "var(--color-text-primary)",
          textAlign: "left",
        }}
      >
        <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>
          {open ? "▼" : "▶"}
        </span>
        Run evaluation
      </button>

      {/* Success banner — outside collapsible so it persists after collapse */}
      {success && (
        <div
          style={{
            padding: "0.625rem 1rem",
            fontSize: "0.875rem",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color:
              success.label === "Ships"
                ? "var(--color-text-success)"
                : "var(--color-text-danger)",
            background:
              success.label === "Ships"
                ? "var(--color-background-success)"
                : "var(--color-background-danger)",
          }}
        >
          <span>Run complete — {success.label}</span>
          {success.score !== null && success.score > 0 && (
            <ScoreBar
              value={success.score}
              max={5}
              barColor={
                success.score >= 4.0
                  ? "var(--color-text-success)"
                  : "var(--color-text-danger)"
              }
            />
          )}
        </div>
      )}

      {/* Collapsible form */}
      {open && (
        <form
          onSubmit={handleSubmit}
          style={{
            padding: "1rem",
            borderTop: "1px solid var(--color-border)",
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
          }}
        >
          {/* Prompt */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label
              style={{
                fontSize: "0.75rem",
                fontWeight: 500,
                color: "var(--color-text-secondary)",
              }}
            >
              Prompt
            </label>
            <select
              value={promptName}
              onChange={(e) => setPromptName(e.target.value)}
              disabled={loading}
              style={inputStyle}
            >
              <option value="">Select a prompt…</option>
              {prompts.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name} (latest: v{p.latest_version})
                </option>
              ))}
            </select>
          </div>

          {/* User message */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label
              style={{
                fontSize: "0.75rem",
                fontWeight: 500,
                color: "var(--color-text-secondary)",
              }}
            >
              User message
            </label>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              rows={3}
              placeholder="e.g. My order hasn't arrived yet"
              style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
            />
          </div>

          {/* Locale */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <label
              style={{
                fontSize: "0.75rem",
                fontWeight: 500,
                color: "var(--color-text-secondary)",
              }}
            >
              Locale
            </label>
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value)}
              disabled={loading}
              style={inputStyle}
            >
              {LOCALES.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {/* Step progress indicator — visible only while loading */}
          {loading && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.75rem",
                padding: "0.5rem 0.75rem",
                borderRadius: "0.375rem",
                background: "var(--color-background-muted)",
              }}
            >
              {STEPS.map(({ n, label }, i) => (
                <span
                  key={n}
                  style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}
                >
                  {i > 0 && (
                    <span style={{ color: "var(--color-text-muted)" }}>→</span>
                  )}
                  <span
                    style={{
                      color:
                        step > n
                          ? "var(--color-text-success)"
                          : step === n
                          ? "var(--color-text-primary)"
                          : "var(--color-text-muted)",
                      fontWeight: step === n ? 600 : 400,
                    }}
                  >
                    {step > n ? "✓" : `${n}.`} {label}
                  </span>
                </span>
              ))}
            </div>
          )}

          {/* Error */}
          {error && (
            <div
              style={{
                padding: "0.5rem 0.75rem",
                borderRadius: "0.375rem",
                background: "var(--color-background-danger)",
                color: "var(--color-text-danger)",
                fontSize: "0.875rem",
              }}
            >
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!canSubmit}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: "0.375rem",
              border: "none",
              background: canSubmit
                ? "var(--color-text-primary)"
                : "var(--color-border)",
              color: canSubmit
                ? "var(--color-surface)"
                : "var(--color-text-muted)",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: canSubmit ? "pointer" : "not-allowed",
              alignSelf: "flex-start",
            }}
          >
            {loading ? "Running…" : "Run evaluation"}
          </button>
        </form>
      )}
    </div>
  );
}
