import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listRuns, listPrompts, getPromptHistory, getLocaleChecks } from "../api/client";
import type { LocaleCheck, PromptSummary, PromptVersion, Run } from "../api/types";
import { PromptFilter } from "../components/PromptFilter";
import { VersionPicker } from "../components/VersionPicker";
import { LocaleGrid } from "../components/LocaleGrid";

export function LocaleBreakdown() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedPrompt = searchParams.get("prompt") ?? "";
  const selectedVersion = searchParams.get("version")
    ? Number(searchParams.get("version"))
    : null;

  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  // run_id → locale checks for that run
  const [checksMap, setChecksMap] = useState<Map<string, LocaleCheck[]>>(new Map());

  const [promptsLoading, setPromptsLoading] = useState(true);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load prompt list once on mount
  useEffect(() => {
    listPrompts()
      .then(setPrompts)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setPromptsLoading(false));
  }, []);

  // Load version history when prompt changes
  useEffect(() => {
    if (!selectedPrompt) {
      setPromptVersions([]);
      return;
    }
    setVersionsLoading(true);
    getPromptHistory(selectedPrompt)
      .then(setPromptVersions)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setVersionsLoading(false));
  }, [selectedPrompt]);

  // Load runs + locale checks when prompt+version both selected
  useEffect(() => {
    if (!selectedPrompt || selectedVersion === null) {
      setRuns([]);
      setChecksMap(new Map());
      return;
    }

    // Find the exact prompt UUID for this (name, version) pair
    const versionRow = promptVersions.find((v) => v.version === selectedVersion);
    if (!versionRow) return;

    let cancelled = false;

    async function load() {
      setDataLoading(true);
      setError(null);
      setChecksMap(new Map());

      try {
        const allRuns = await listRuns(0, 200);
        // Filter by the exact prompt_id UUID — this is why prompt_id is an FK
        // to prompts.id (the exact version row), not just the name+version pair.
        const versionRuns = allRuns.filter((r) => r.prompt_id === versionRow!.id);
        if (cancelled) return;
        setRuns(versionRuns);

        if (versionRuns.length === 0) {
          setDataLoading(false);
          return;
        }

        // Fetch locale checks for each run in parallel — reads, no side effects.
        // Promise.allSettled: a failed fetch means no entry in the map for that
        // run_id. That run contributes no rows to the grid (no pass, no fail, no —).
        const results = await Promise.allSettled(
          versionRuns.map((r) => getLocaleChecks(r.id))
        );
        if (cancelled) return;

        const map = new Map<string, LocaleCheck[]>();
        versionRuns.forEach((r, i) => {
          const result = results[i];
          if (result.status === "fulfilled") {
            map.set(r.id, result.value);
          }
        });
        setChecksMap(map);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setDataLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [selectedPrompt, selectedVersion, promptVersions]);

  // Build grid data from raw LocaleCheck rows.
  // Columns = check_types actually seen in the data (not a hardcoded list).
  // Rows = locales seen in the data.
  // Cell aggregation: fail-closed — any passed=false for (locale, check_type)
  // across all runs for this version → the cell shows fail.
  const gridData = useMemo(() => {
    const cellResults = new Map<string, Map<string, boolean>>();

    for (const run of runs) {
      const checks = checksMap.get(run.id) ?? [];
      for (const check of checks) {
        if (!cellResults.has(check.locale)) {
          cellResults.set(check.locale, new Map());
        }
        const localeRow = cellResults.get(check.locale)!;
        const current = localeRow.get(check.check_type);
        // Once false, stays false — any failure poisons the cell
        localeRow.set(
          check.check_type,
          current === undefined ? check.passed : current && check.passed
        );
      }
    }

    const checkTypesSet = new Set<string>();
    const localesSet = new Set<string>();
    for (const [locale, ctMap] of cellResults) {
      localesSet.add(locale);
      for (const ct of ctMap.keys()) checkTypesSet.add(ct);
    }

    return {
      checkTypes: Array.from(checkTypesSet).sort(),
      locales: Array.from(localesSet).sort(),
      cells: cellResults,
    };
  }, [runs, checksMap]);

  const hasNoChecks =
    !dataLoading &&
    runs.length > 0 &&
    gridData.checkTypes.length === 0;

  function handlePromptChange(name: string) {
    if (name) {
      setSearchParams({ prompt: name });
    } else {
      setSearchParams({});
    }
  }

  function handleVersionChange(version: number | null) {
    if (version !== null) {
      setSearchParams({ prompt: selectedPrompt, version: String(version) });
    } else {
      setSearchParams({ prompt: selectedPrompt });
    }
  }

  if (error) {
    return (
      <div
        style={{
          padding: "1rem",
          borderRadius: "0.5rem",
          background: "var(--color-background-danger)",
          color: "var(--color-text-danger)",
        }}
      >
        Error: {error}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div>
          <h2 style={{ margin: "0 0 0.25rem", fontSize: "1rem", fontWeight: 600 }}>
            Locale Breakdown
          </h2>
          <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--color-text-secondary)" }}>
            Each cell shows whether the LLM output met locale-specific requirements.{" "}
            <span style={{ color: "var(--color-text-danger)", fontWeight: 500 }}>Red</span>{" "}
            means the output would fail in that market.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          {promptsLoading ? (
            <span style={{ fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
              Loading prompts…
            </span>
          ) : (
            <PromptFilter
              prompts={prompts}
              value={selectedPrompt}
              onChange={handlePromptChange}
            />
          )}

          {selectedPrompt && !versionsLoading && promptVersions.length > 0 && (
            <VersionPicker
              versions={promptVersions}
              value={selectedVersion}
              onChange={handleVersionChange}
            />
          )}
        </div>
      </div>

      {!selectedPrompt ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          Select a prompt above to inspect its locale check results.
        </p>
      ) : selectedVersion === null ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          Select a version to see the locale breakdown grid.
        </p>
      ) : dataLoading ? (
        <p style={{ color: "var(--color-text-muted)" }}>Loading locale checks…</p>
      ) : runs.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          No runs yet for <strong>{selectedPrompt}</strong> v{selectedVersion}.
        </p>
      ) : hasNoChecks ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          No locale checks run yet for <strong>{selectedPrompt}</strong> v{selectedVersion}.
          Call <code>POST /v1/evaluate-locale/{"{prompt_id}"}</code> first.
        </p>
      ) : (
        <section
          style={{
            border: `1px solid var(--color-border)`,
            borderRadius: "0.5rem",
            padding: "1rem",
            background: "var(--color-surface)",
          }}
        >
          <h3
            style={{
              margin: "0 0 0.75rem",
              fontSize: "0.875rem",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
            }}
          >
            Locale check results — {selectedPrompt} v{selectedVersion}
          </h3>
          <LocaleGrid
            checkTypes={gridData.checkTypes}
            locales={gridData.locales}
            cells={gridData.cells}
          />
        </section>
      )}
    </div>
  );
}
