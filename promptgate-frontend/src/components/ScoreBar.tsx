interface Props {
  value: number;
  max: number;
  barColor: string;  // CSS var, e.g. "var(--color-text-success)"
  width?: number;    // px, default 80
  label?: string;    // override displayed text, default value.toFixed(1)
}

export function ScoreBar({ value, max, barColor, width = 80, label }: Props) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const displayLabel = label ?? value.toFixed(1);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
      <div
        style={{
          width: `${width}px`,
          height: "6px",
          borderRadius: "3px",
          background: "var(--color-background-muted)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            borderRadius: "3px",
            background: barColor,
          }}
        />
      </div>
      <span style={{ fontSize: "0.8125rem", color: "var(--color-text-secondary)" }}>
        {displayLabel}
      </span>
    </div>
  );
}
