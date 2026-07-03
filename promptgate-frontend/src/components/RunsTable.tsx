import { useEffect, useRef, useState } from "react";
import type { Run, Verdict } from "../api/types";
import { VerdictBadge } from "./VerdictBadge";
import { BlockedReasons } from "./BlockedReasons";
import { PassedReasons } from "./PassedReasons";
import { ScoreBar } from "./ScoreBar";

export interface RunRow {
  run: Run;
  verdict: Verdict | null;
  verdictError: string | null;
}

interface Props {
  rows: RunRow[];
}

// 7 columns: Created / Locale / Prompt / Score / Verdict / i18n / Output
const COL_SPAN = 7;

export function RunsTable({ rows }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const autoExpandedRef = useRef(false);

  // Pre-expand the first blocked row once verdicts load.
  // autoExpandedRef guards against re-running after the user manually
  // collapses a row — their click should not be overridden on re-render.
  useEffect(() => {
    if (autoExpandedRef.current) return;
    const firstBlocked = rows.find(
      (r) => r.verdict !== null && !r.verdict.can_ship
    );
    if (firstBlocked) {
      setExpandedId(firstBlocked.run.id);
      autoExpandedRef.current = true;
    }
  }, [rows]);

  if (rows.length === 0) {
    return (
      <p style={{ color: "var(--color-text-muted)", padding: "1rem 0" }}>
        No runs match the current filter.
      </p>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
        <thead>
          <tr
            style={{
              borderBottom: `1px solid var(--color-border)`,
              color: "var(--color-text-secondary)",
              textAlign: "left",
            }}
          >
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>Created</th>
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>Locale</th>
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>Prompt</th>
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>Score</th>
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>Verdict</th>
            <th style={{ padding: "0.5rem 1rem 0.5rem 0", fontWeight: 500 }}>i18n</th>
            <th style={{ padding: "0.5rem 0 0.5rem 0", fontWeight: 500 }}>Output</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ run, verdict, verdictError }) => {
            const isBlocked = verdict !== null && !verdict.can_ship;
            const canExpand = verdict !== null;
            const isExpanded = expandedId === run.id;

            // Locale check signal — built from verdict.locale_results already in the
            // verdicts Map; no additional fetch. Each run has exactly one locale.
            const localeResults = verdict?.locale_results ?? [];
            const isChecked = localeResults.length > 0;
            const allPassed = isChecked && localeResults.every((c) => c.passed);
            const dotColor = !isChecked
              ? "var(--color-text-muted)"
              : allPassed
              ? "var(--color-text-success)"
              : "var(--color-text-danger)";
            const localeTooltip = isChecked
              ? `${run.locale}: ${localeResults
                  .map((c) => `${c.check_type} ${c.passed ? "✓" : "✗"}`)
                  .join(", ")}`
              : `${run.locale}: not checked`;

            return (
              <>
                <tr
                  key={run.id}
                  onClick={() => {
                    if (canExpand) setExpandedId(isExpanded ? null : run.id);
                  }}
                  style={{
                    borderBottom: isExpanded ? "none" : `1px solid var(--color-border)`,
                    background: isExpanded ? "var(--color-surface-hover)" : undefined,
                    cursor: canExpand ? "pointer" : "default",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLTableRowElement).style.background =
                      "var(--color-surface-hover)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLTableRowElement).style.background = isExpanded
                      ? "var(--color-surface-hover)"
                      : "";
                  }}
                >
                  <td
                    style={{
                      padding: "0.5rem 1rem 0.5rem 0",
                      whiteSpace: "nowrap",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "0.5rem 1rem 0.5rem 0" }}>{run.locale}</td>
                  <td style={{ padding: "0.5rem 1rem 0.5rem 0" }}>
                    {run.prompt_name}{" "}
                    <span style={{ color: "var(--color-text-muted)", fontSize: "0.75rem" }}>
                      v{run.version}
                    </span>
                  </td>
                  {/* Score bar: null or 0.0 (judge failed) → muted dash */}
                  <td style={{ padding: "0.5rem 1rem 0.5rem 0" }}>
                    {run.score === null || run.score === 0 ? (
                      <span
                        style={{ color: "var(--color-text-muted)" }}
                        title={
                          run.score === 0
                            ? (run.judge_reasoning ?? "judge call failed")
                            : undefined
                        }
                      >
                        —
                      </span>
                    ) : (
                      <ScoreBar
                        value={run.score}
                        max={5}
                        barColor={
                          run.score >= 4.0
                            ? "var(--color-text-success)"
                            : "var(--color-text-danger)"
                        }
                      />
                    )}
                  </td>
                  <td style={{ padding: "0.5rem 1rem 0.5rem 0" }}>
                    <VerdictBadge verdict={verdict} error={verdictError} />
                    {canExpand && (
                      <span
                        style={{
                          marginLeft: "0.375rem",
                          fontSize: "0.7rem",
                          // Blocked rows: secondary (draws eye); shipped rows: muted (de-emphasised)
                          color: isBlocked
                            ? "var(--color-text-secondary)"
                            : "var(--color-text-muted)",
                        }}
                      >
                        {isExpanded ? "▲" : "▼"}
                      </span>
                    )}
                  </td>
                  {/* Locale check signal: one dot per run, color-coded by pass/fail */}
                  <td style={{ padding: "0.5rem 1rem 0.5rem 0" }}>
                    <span
                      title={localeTooltip}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.3rem",
                        fontSize: "0.75rem",
                        color: "var(--color-text-secondary)",
                        cursor: "default",
                      }}
                    >
                      <span
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          background: dotColor,
                          flexShrink: 0,
                          display: "inline-block",
                        }}
                      />
                      {run.locale}
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "0.5rem 0 0.5rem 0",
                      maxWidth: "20rem",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: "var(--color-text-secondary)",
                    }}
                    title={run.output}
                  >
                    {run.output}
                  </td>
                </tr>
                {isExpanded && verdict && !verdict.can_ship && (
                  <BlockedReasons reasons={verdict.reasons} colSpan={COL_SPAN} output={run.output} />
                )}
                {isExpanded && verdict && verdict.can_ship && (
                  <PassedReasons verdict={verdict} locale={run.locale} colSpan={COL_SPAN} output={run.output} />
                )}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
