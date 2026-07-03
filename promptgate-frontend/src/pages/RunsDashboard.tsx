import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listRuns, listPrompts, evaluateRun } from "../api/client";
import type { Run, PromptSummary, Verdict } from "../api/types";
import { RunsTable, type RunRow } from "../components/RunsTable";
import { PromptFilter } from "../components/PromptFilter";
import { EvalPanel } from "../components/EvalPanel";

// Inline stat card — only used on this page
function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div
      style={{
        flex: 1,
        padding: "0.875rem 1rem",
        border: "1px solid var(--color-border)",
        borderRadius: "0.5rem",
        background: "var(--color-surface)",
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: "0.6875rem",
          fontWeight: 500,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "0.25rem",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "1.5rem",
          fontWeight: 600,
          color: color ?? "var(--color-text-primary)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export function RunsDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const promptFilter = searchParams.get("prompt") ?? "";

  const [runs, setRuns] = useState<Run[]>([]);
  const [verdicts, setVerdicts] = useState<Map<string, { verdict: Verdict | null; error: string | null }>>(new Map());
  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [fetchedRuns, fetchedPrompts] = await Promise.all([
          listRuns(0, 50),
          listPrompts(),
        ]);
        if (cancelled) return;

        setRuns(fetchedRuns);
        setPrompts(fetchedPrompts);

        // Seed verdicts map with nulls so table shows "checking…" immediately
        setVerdicts(new Map(fetchedRuns.map((r) => [r.id, { verdict: null, error: null }])));

        // Promise.allSettled: one failing /v1/evaluate call shows an error badge
        // on that row — it does not crash the rest of the table (Promise.all would).
        const results = await Promise.allSettled(
          fetchedRuns.map((r) => evaluateRun(r.id))
        );
        if (cancelled) return;

        const map = new Map<string, { verdict: Verdict | null; error: string | null }>();
        fetchedRuns.forEach((r, i) => {
          const result = results[i];
          if (result.status === "fulfilled") {
            map.set(r.id, { verdict: result.value, error: null });
          } else {
            map.set(r.id, { verdict: null, error: result.reason instanceof Error ? result.reason.message : String(result.reason) });
          }
        });
        setVerdicts(map);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [refreshKey]);

  const filteredRows = useMemo<RunRow[]>(() => {
    const filtered = promptFilter
      ? runs.filter((r) => r.prompt_name === promptFilter)
      : runs;
    return filtered.map((r) => ({
      run: r,
      verdict: verdicts.get(r.id)?.verdict ?? null,
      verdictError: verdicts.get(r.id)?.error ?? null,
    }));
  }, [runs, verdicts, promptFilter]);

  // Stats derived from filtered rows — no new API calls, built from verdicts
  // already fetched by Promise.allSettled. Updates automatically on filter change.
  const stats = useMemo(() => {
    const total = filteredRows.length;
    const shipped = filteredRows.filter((r) => r.verdict?.can_ship === true).length;
    const blocked = filteredRows.filter(
      (r) => r.verdict !== null && r.verdict.can_ship === false
    ).length;
    const rate = total === 0 ? null : (shipped / total) * 100;
    return { total, shipped, blocked, rate };
  }, [filteredRows]);

  function handleFilterChange(name: string) {
    if (name) {
      setSearchParams({ prompt: name });
    } else {
      setSearchParams({});
    }
  }

  function handleRunComplete() {
    setRefreshKey((k) => k + 1);
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
        Failed to load runs: {error}
      </div>
    );
  }

  const dash = "—";
  const rateColor =
    loading || stats.rate === null
      ? undefined
      : stats.rate >= 80
      ? "var(--color-text-success)"
      : stats.rate < 50
      ? "var(--color-text-danger)"
      : "var(--color-text-warning)";

  return (
    <div>
      {/* Stat cards — above EvalPanel, derived from already-fetched verdict data */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        <StatCard
          label="Total runs"
          value={loading ? dash : String(stats.total)}
        />
        <StatCard
          label="Shipped"
          value={loading ? dash : String(stats.shipped)}
          color="var(--color-text-success)"
        />
        <StatCard
          label="Blocked"
          value={loading ? dash : String(stats.blocked)}
          color="var(--color-text-danger)"
        />
        <StatCard
          label="Ship rate"
          value={
            loading || stats.rate === null
              ? dash
              : `${stats.rate.toFixed(0)}%`
          }
          color={rateColor}
        />
      </div>

      <EvalPanel prompts={prompts} onRunComplete={handleRunComplete} />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "1rem",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Recent runs</h2>
        <PromptFilter
          prompts={prompts}
          value={promptFilter}
          onChange={handleFilterChange}
        />
      </div>

      {loading && runs.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>Loading runs…</p>
      ) : (
        <RunsTable rows={filteredRows} />
      )}
    </div>
  );
}
