import type { PromptSummary } from "../api/types";

interface Props {
  prompts: PromptSummary[];
  value: string;
  onChange: (name: string) => void;
}

export function PromptFilter({ prompts, value, onChange }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <label
        htmlFor="prompt-filter"
        style={{ fontSize: "0.875rem", color: "var(--color-text-secondary)" }}
      >
        Prompt
      </label>
      <select
        id="prompt-filter"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          fontSize: "0.875rem",
          padding: "0.25rem 0.5rem",
          borderRadius: "0.375rem",
          border: `1px solid var(--color-border)`,
          background: "var(--color-surface)",
          color: "var(--color-text-primary)",
          cursor: "pointer",
        }}
      >
        <option value="">All prompts</option>
        {prompts.map((p) => (
          <option key={p.name} value={p.name}>
            {p.name} (v{p.latest_version})
          </option>
        ))}
      </select>
    </div>
  );
}
