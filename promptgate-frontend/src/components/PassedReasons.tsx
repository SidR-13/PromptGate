import { useState } from "react";
import type { Verdict } from "../api/types";

interface Props {
  verdict: Verdict;
  locale: string;
  colSpan: number;
  output: string | null;
}

export function PassedReasons({ verdict, locale, colSpan, output }: Props) {
  const [expanded, setExpanded] = useState(false);

  const localeResults = verdict.locale_results ?? [];

  const uniqueChecks = localeResults.filter(
    (check, index, self) =>
      index === self.findIndex((c) => c.check_type === check.check_type)
  );

  const summaryBullets: string[] = [];
  if (verdict.eval_score !== null && verdict.eval_score > 0) {
    summaryBullets.push(`eval score ${verdict.eval_score.toFixed(1)} ≥ threshold 4.0`);
  }
  if (!verdict.blocked) {
    summaryBullets.push("moderation: clean");
  }
  if (uniqueChecks.length > 0 && uniqueChecks.every((c) => c.passed)) {
    summaryBullets.push(`locale checks: all passed (${locale})`);
  }

  return (
    <tr>
      <td
        colSpan={colSpan}
        style={{
          padding: "0.5rem 1rem 0.75rem 1.5rem",
          background: "var(--color-surface)",
          boxShadow: "inset 3px 0 0 var(--color-text-success)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <p
          style={{
            margin: "0 0 0.25rem",
            fontSize: "0.75rem",
            fontWeight: 600,
            color: "var(--color-text-success)",
          }}
        >
          Passed — reasons:
        </p>
        <ul
          style={{
            margin: 0,
            paddingLeft: 0,
            fontSize: "0.75rem",
            listStyleType: "none",
            display: "flex",
            flexDirection: "column",
            gap: "0.125rem",
          }}
        >
          {summaryBullets.map((b, i) => (
            <li key={i} style={{ display: "flex", alignItems: "baseline", gap: "0.375rem" }}>
              <span style={{ color: "var(--color-text-success)", flexShrink: 0 }}>✓</span>
              <span style={{ color: "var(--color-text-primary)" }}>{b}</span>
            </li>
          ))}
          {uniqueChecks
            .filter((c) => c.passed)
            .map((c, i) => (
              <li
                key={`lc-${i}`}
                style={{ display: "flex", alignItems: "baseline", gap: "0.375rem", paddingLeft: "1rem" }}
              >
                <span style={{ color: "var(--color-text-success)", flexShrink: 0 }}>✓</span>
                <span style={{ color: "var(--color-text-primary)" }}>locale {c.check_type}</span>
              </li>
            ))}
        </ul>
        {output && (
          <div style={{ marginTop: "0.75rem" }}>
            <p
              style={{
                margin: "0 0 0.25rem",
                fontSize: "11px",
                fontWeight: 500,
                letterSpacing: "0.05em",
                color: "var(--color-text-tertiary)",
                textTransform: "uppercase",
              }}
            >
              Output
            </p>
            <div
              style={{
                position: "relative",
                overflow: "hidden",
                maxHeight: expanded ? "none" : "160px",
                padding: "0.75rem",
                borderRadius: "var(--border-radius-md)",
                border: "0.5px solid var(--color-border-tertiary)",
                background: "var(--color-background-secondary)",
                fontSize: "0.75rem",
                color: "var(--color-text-primary)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                cursor: expanded ? "default" : "pointer",
              }}
              onClick={() => { if (!expanded) setExpanded(true); }}
            >
              {output}
              {!expanded && (
                <div
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: "60px",
                    background: "linear-gradient(to bottom, transparent, var(--color-background-secondary))",
                    pointerEvents: "none",
                  }}
                />
              )}
            </div>
            <button
              type="button"
              onClick={() => setExpanded((e) => !e)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "11px",
                color: "var(--color-text-tertiary)",
                padding: "4px 0 0 0",
                display: "block",
              }}
            >
              {expanded ? "Show less ↑" : "Show more ↓"}
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}
