import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { listRuns } from "../api/client";
import type { Run } from "../api/types";

interface ChartPoint {
  date: string;
  score: number | null;
  runId: string;
}

/**
 * score=NULL (not yet evaluated) is excluded entirely — it's not a result.
 *
 * score=0.0 is never a legitimate judge score (judge() clamps real scores to
 * [1.0, 5.0]; 0.0 only ever comes from a judge-call failure). Plotting it as
 * a normal point — even in a different color — would still occupy y=0 on the
 * line and read as "the prompt cratered." Instead it becomes a gap in the
 * line (connectNulls=false) plus a labeled vertical ReferenceLine, so a judge
 * infrastructure failure is visible but never implies a quality regression.
 */
function toChartData(runs: Run[]): { points: ChartPoint[]; failures: ChartPoint[] } {
  const sorted = [...runs].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const points: ChartPoint[] = [];
  const failures: ChartPoint[] = [];

  for (const run of sorted) {
    if (run.score === null) continue; // not yet evaluated — not a result

    const date = new Date(run.created_at).toLocaleDateString();
    if (run.score === 0) {
      points.push({ date, score: null, runId: run.id }); // gap in the line
      failures.push({ date, score: 0, runId: run.id });
    } else {
      points.push({ date, score: run.score, runId: run.id });
    }
  }

  return { points, failures };
}

export function ScoreTrendChart() {
  const [points, setPoints] = useState<ChartPoint[]>([]);
  const [failures, setFailures] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listRuns(0, 200).then((runs) => {
      const { points, failures } = toChartData(runs);
      setPoints(points);
      setFailures(failures);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="text-gray-400 p-4">Loading chart…</div>;
  if (points.length === 0) {
    return <div className="text-gray-400 p-4">No evaluated runs yet — score chart needs at least one judged run.</div>;
  }

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={[1, 5]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            connectNulls={false}
            dot={{ r: 3 }}
            name="Judge score"
          />
          {failures.map((f) => (
            <ReferenceLine
              key={f.runId}
              x={f.date}
              stroke="#dc2626"
              strokeDasharray="4 4"
              label={{ value: "judge failed", position: "top", fill: "#dc2626", fontSize: 10 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
