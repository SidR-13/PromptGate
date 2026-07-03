import { useState } from "react";

interface Props {
  reasons: string[];
  colSpan: number;
  output: string | null;
}

export function BlockedReasons({ reasons, colSpan, output }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <tr>
      <td
        colSpan={colSpan}
        style={{
          padding: "0.5rem 1rem 0.75rem 1.5rem",
          background: "var(--color-surface)",
          boxShadow: "inset 3px 0 0 var(--color-text-danger)",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <p
          style={{
            margin: "0 0 0.25rem",
            fontSize: "0.75rem",
            fontWeight: 600,
            color: "var(--color-text-danger)",
          }}
        >
          Blocked — reasons:
        </p>
        <ul
          style={{
            margin: 0,
            paddingLeft: "1.25rem",
            fontSize: "0.75rem",
            color: "var(--color-text-primary)",
          }}
        >
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
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
