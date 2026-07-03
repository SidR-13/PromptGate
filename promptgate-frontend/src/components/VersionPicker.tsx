import type { PromptVersion } from "../api/types";

interface Props {
  versions: PromptVersion[];
  value: number | null;
  onChange: (version: number | null) => void;
}

export function VersionPicker({ versions, value, onChange }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <label
        htmlFor="version-picker"
        style={{ fontSize: "0.875rem", color: "var(--color-text-secondary)" }}
      >
        Version
      </label>
      <select
        id="version-picker"
        value={value ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "" ? null : Number(v));
        }}
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
        <option value="">Select version</option>
        {versions.map((v) => (
          <option key={v.version} value={v.version}>
            v{v.version}
          </option>
        ))}
      </select>
    </div>
  );
}
