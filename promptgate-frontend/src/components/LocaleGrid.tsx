const CHECK_TYPE_SUBTITLES: Record<string, string> = {
  date: "Format (MM/DD vs DD/MM)",
  number: "Grouping & decimals",
  script: "Correct writing system",
  rtl: "Right-to-left direction",
};

const LOCALE_NAMES: Record<string, string> = {
  "en-US": "English (US)",
  "ar-SA": "Arabic (Saudi)",
  "ja-JP": "Japanese",
  "de-DE": "German",
  "fr-FR": "French",
};

const CELL_BORDER = "0.5px solid var(--color-border)";
const CELL_HEIGHT = "44px";

interface Props {
  checkTypes: string[];
  locales: string[];
  // locale → check_type → passed (absent = not applicable for this locale)
  cells: Map<string, Map<string, boolean>>;
}

function Cell({ value }: { value: boolean | undefined }) {
  if (value === undefined) {
    return (
      <td
        style={{
          height: CELL_HEIGHT,
          padding: "0 0.75rem",
          textAlign: "center",
          verticalAlign: "middle",
          color: "var(--color-text-muted)",
          fontSize: "0.875rem",
          border: CELL_BORDER,
        }}
      >
        —
      </td>
    );
  }

  return (
    <td
      style={{
        height: CELL_HEIGHT,
        padding: "0 0.75rem",
        textAlign: "center",
        verticalAlign: "middle",
        fontSize: "1rem",
        color: value ? "var(--color-text-success)" : "var(--color-text-danger)",
        background: value
          ? "var(--color-background-success)"
          : "var(--color-background-danger)",
        border: CELL_BORDER,
      }}
    >
      {value ? "✓" : "✗"}
    </td>
  );
}

export function LocaleGrid({ checkTypes, locales, cells }: Props) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.875rem", minWidth: "100%" }}>
        <thead>
          <tr style={{ borderBottom: `1px solid var(--color-border)` }}>
            <th
              style={{
                padding: "0.5rem 1.5rem 0.5rem 1rem",
                textAlign: "left",
                fontWeight: 500,
                color: "var(--color-text-secondary)",
                whiteSpace: "nowrap",
                border: CELL_BORDER,
              }}
            >
              Locale
            </th>
            {checkTypes.map((ct) => (
              <th
                key={ct}
                style={{
                  padding: "0.5rem 1rem",
                  textAlign: "center",
                  fontWeight: 500,
                  color: "var(--color-text-secondary)",
                  whiteSpace: "nowrap",
                  border: CELL_BORDER,
                }}
              >
                <div>{ct.replace("_", " ")}</div>
                {CHECK_TYPE_SUBTITLES[ct] && (
                  <div
                    style={{
                      fontSize: "11px",
                      fontWeight: 400,
                      color: "var(--color-text-muted)",
                      marginTop: "0.125rem",
                    }}
                  >
                    {CHECK_TYPE_SUBTITLES[ct]}
                  </div>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {locales.map((locale) => (
            <tr key={locale}>
              <td
                style={{
                  height: CELL_HEIGHT,
                  padding: "0 1.5rem 0 1rem",
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                  verticalAlign: "middle",
                  border: CELL_BORDER,
                }}
              >
                {locale}{" "}
                {LOCALE_NAMES[locale] && (
                  <span
                    style={{
                      fontWeight: 400,
                      color: "var(--color-text-muted)",
                      marginLeft: "0.375rem",
                    }}
                  >
                    {LOCALE_NAMES[locale]}
                  </span>
                )}
              </td>
              {checkTypes.map((ct) => (
                <Cell key={ct} value={cells.get(locale)?.get(ct)} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
