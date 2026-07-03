import type { Verdict } from "../api/types";

interface Props {
  verdict: Verdict | null;
  error: string | null;
}

export function VerdictBadge({ verdict, error }: Props) {
  if (error) {
    return (
      <span
        style={{
          padding: "0.125rem 0.5rem",
          borderRadius: "0.25rem",
          fontSize: "0.75rem",
          background: "var(--color-background-muted)",
          color: "var(--color-text-muted)",
        }}
        title={error}
      >
        error
      </span>
    );
  }

  if (verdict === null) {
    return (
      <span
        style={{
          padding: "0.125rem 0.5rem",
          borderRadius: "0.25rem",
          fontSize: "0.75rem",
          background: "var(--color-background-muted)",
          color: "var(--color-text-muted)",
          opacity: 0.6,
        }}
      >
        checking…
      </span>
    );
  }

  return verdict.can_ship ? (
    <span
      style={{
        padding: "0.125rem 0.5rem",
        borderRadius: "0.25rem",
        fontSize: "0.75rem",
        fontWeight: 500,
        background: "var(--color-background-success)",
        color: "var(--color-text-success)",
      }}
    >
      CAN SHIP
    </span>
  ) : (
    <span
      style={{
        padding: "0.125rem 0.5rem",
        borderRadius: "0.25rem",
        fontSize: "0.75rem",
        fontWeight: 500,
        background: "var(--color-background-danger)",
        color: "var(--color-text-danger)",
      }}
    >
      BLOCKED
    </span>
  );
}
