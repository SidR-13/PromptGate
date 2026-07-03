import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listRuns, listPrompts, getLocaleChecks } from "../api/client";
import type { LocaleCheck, PromptSummary, Run } from "../api/types";
import { PromptFilter } from "../components/PromptFilter";
import { ScoreTrendChart } from "../components/ScoreTrendChart";
import { VersionShipRateTable, type VersionStat } from "../components/VersionShipRateTable";

export function PromptDetail() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedPrompt = searchParams.get("prompt") ?? "";

  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  // Map from run_id → locale checks for that run. Missing key = fetch failed (fail-closed).
  const [localeMap, setLocaleMap] = useState<Map<string, LocaleCheck[]>>(new Map());

  const [promptsLoading, setPromptsLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(false);
  const [localeLoading, setLocaleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load prompt list once on mount
  useEffect(() => {
    listPrompts()
      .then(setPrompts)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setPromptsLoading(false));
  }, []);

  // Reload runs + locale checks whenever the selected prompt changes
  useEffect(() => {
    if (!selectedPrompt) {
      setRuns([]);
      setLocaleMap(new Map());
      return;
    }

    let cancelled = false;

    async function load() {
      setRunsLoading(true);
      setLocaleLoading(true);
      setError(null);
      setLocaleMap(new Map());

      try {
        const allRuns = await listRuns(0, 200);
        const promptRuns = allRuns.filter((r) => r.prompt_name === selectedPrompt);
        if (cancelled) return;
        setRuns(promptRuns);
        setRunsLoading(false);

        if (promptRuns.length === 0) {
          setLocaleLoading(false);
          return;
        }

        // Locale checks are reads — no side effects. One GET per run, parallel.
        // Promise.allSettled: a failed fetch means we can't confirm locale for
        // that run, so it falls through as "no checks found" → not shippable
        // (fail-closed, same logic as build_verdict).
        const results = await Promise.allSettled(
          promptRuns.map((r) => getLocaleChecks(r.id))
        );
        if (cancelled) return;

        const map = new Map<string, LocaleCheck[]>();
        promptRuns.forEach((r, i) => {
          const result = results[i];
          if (result.status === "fulfilled") {
            map.set(r.id, result.value);
          }
          // On rejection: no entry → fail-closed in versionStats below
        });
        setLocaleMap(map);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLocaleLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [selectedPrompt]);

  // Per-version ship rate computed from raw Run fields + locale check rows.
  // can_ship = score >= 4.0 AND NOT blocked AND locale checks exist AND all passed.
  //
  // Three distinct states for locale checks on a given run:
  //   checks === undefined  → fetch failed (network error) — fail-closed, not counted
  //   checks.length === 0   → fetch succeeded, no locale checks run yet — not shipped,
  //                           tracked separately as unevaluated_count so the UI can
  //                           distinguish "0% because checks failed" from "0% because
  //                           checks were never run" (same intent as score=0.0 annotation)
  //   checks.length > 0     → checks ran; pass/fail determined by all(passed)
  const versionStats = useMemo<VersionStat[]>(() => {
    if (localeLoading) return [];

    const stats = new Map<number, { run_count: number; shipped: number; unevaluated_count: number }>();

    for (const run of runs) {
      const checks = localeMap.get(run.id);
      const localeOk =
        checks !== undefined && checks.length > 0 && checks.every((c) => c.passed);
      const canShip =
        run.score !== null && run.score >= 4.0 && !run.blocked && localeOk;
      const localeUnevaluated = checks !== undefined && checks.length === 0;

      if (!stats.has(run.version)) {
        stats.set(run.version, { run_count: 0, shipped: 0, unevaluated_count: 0 });
      }
      const s = stats.get(run.version)!;
      s.run_count++;
      if (canShip) s.shipped++;
      if (localeUnevaluated) s.unevaluated_count++;
    }

    return Array.from(stats.entries())
      .sort(([a], [b]) => a - b)
      .map(([version, { run_count, shipped, unevaluated_count }]) => ({
        version,
        run_count,
        shipped,
        unevaluated_count,
      }));
  }, [runs, localeMap, localeLoading]);

  function handlePromptChange(name: string) {
    if (name) {
      setSearchParams({ prompt: name });
    } else {
      setSearchParams({});
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
            Prompt Trends
          </h2>
          <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--color-text-secondary)" }}>
            Track how output quality changes as prompts evolve. A score below{" "}
            <span style={{ color: "var(--color-text-warning)", fontWeight: 500 }}>4.0</span>{" "}
            blocks shipping.
          </p>
        </div>
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
      </div>

      {!selectedPrompt ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          Select a prompt above to see its score trend and version ship rates.
        </p>
      ) : runsLoading ? (
        <p style={{ color: "var(--color-text-muted)" }}>Loading runs…</p>
      ) : runs.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          No runs yet for <strong>{selectedPrompt}</strong>. Generate some runs first.
        </p>
      ) : (
        <>
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
              Score over time{" "}
              <span style={{ fontWeight: 400, color: "var(--color-text-muted)" }}>
                — {selectedPrompt}
              </span>
            </h3>
            <ScoreTrendChart runs={runs} />
          </section>

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
              Ship rate by version
            </h3>
            <VersionShipRateTable
              stats={versionStats}
              loading={localeLoading}
            />
          </section>
        </>
      )}
    </div>
  );
}
