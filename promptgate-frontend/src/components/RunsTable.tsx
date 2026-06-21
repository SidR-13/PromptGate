import { useEffect, useState } from "react";
import { listRuns, evaluateRun } from "../api/client";
import type { Run, Verdict } from "../api/types";

interface RunRow {
  run: Run;
  verdict: Verdict | null;
  verdictError: string | null;
}

function ShipBadge({ verdict, error }: { verdict: Verdict | null; error: string | null }) {
  if (error) {
    return <span className="px-2 py-1 text-xs rounded bg-gray-200 text-gray-600">verdict error</span>;
  }
  if (verdict === null) {
    return <span className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-400 animate-pulse">checking…</span>;
  }
  return verdict.can_ship ? (
    <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-700 font-medium">CAN SHIP</span>
  ) : (
    <span
      className="px-2 py-1 text-xs rounded bg-red-100 text-red-700 font-medium cursor-help"
      title={verdict.reasons.join("\n")}
    >
      BLOCKED
    </span>
  );
}

export function RunsTable() {
  const [rows, setRows] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const runs = await listRuns(0, 50);
        if (cancelled) return;
        setRows(runs.map((run) => ({ run, verdict: null, verdictError: null })));

        // can_ship badges are fetched live from POST /v1/evaluate, never a
        // stored field. Parallelized so a 50-row page doesn't serialize
        // 50 sequential round trips.
        const verdicts = await Promise.all(
          runs.map((run) =>
            evaluateRun(run.id)
              .then((v) => ({ verdict: v, verdictError: null }))
              .catch((e: Error) => ({ verdict: null, verdictError: e.message }))
          )
        );
        if (cancelled) return;
        setRows(runs.map((run, i) => ({ run, ...verdicts[i] })));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <div className="text-red-600 p-4">Failed to load runs: {error}</div>;
  }

  if (loading && rows.length === 0) {
    return <div className="text-gray-400 p-4">Loading runs…</div>;
  }

  if (rows.length === 0) {
    return <div className="text-gray-400 p-4">No runs yet.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left text-gray-500 border-b">
            <th className="py-2 pr-4">Created</th>
            <th className="py-2 pr-4">Locale</th>
            <th className="py-2 pr-4">Score</th>
            <th className="py-2 pr-4">Moderation</th>
            <th className="py-2 pr-4">Verdict</th>
            <th className="py-2 pr-4">Output</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ run, verdict, verdictError }) => (
            <tr key={run.id} className="border-b hover:bg-gray-50">
              <td className="py-2 pr-4 whitespace-nowrap text-gray-500">
                {new Date(run.created_at).toLocaleString()}
              </td>
              <td className="py-2 pr-4">{run.locale}</td>
              <td className="py-2 pr-4">
                {run.score === null ? (
                  <span className="text-gray-400">—</span>
                ) : run.score === 0 ? (
                  <span className="text-red-600" title={run.judge_reasoning ?? ""}>
                    failed
                  </span>
                ) : (
                  run.score.toFixed(1)
                )}
              </td>
              <td className="py-2 pr-4">
                {run.blocked ? (
                  <span className="text-red-600" title={run.block_reason ?? ""}>
                    blocked
                  </span>
                ) : (
                  <span className="text-gray-400">clear</span>
                )}
              </td>
              <td className="py-2 pr-4">
                <ShipBadge verdict={verdict} error={verdictError} />
              </td>
              <td className="py-2 pr-4 max-w-xs truncate" title={run.output}>
                {run.output}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
