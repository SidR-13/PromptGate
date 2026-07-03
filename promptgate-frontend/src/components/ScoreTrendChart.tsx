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
import type { Run } from "../api/types";

interface ChartPoint {
  date: string;
  score: number | null;
  runId: string;
}

interface ChartData {
  points: ChartPoint[];
  failures: ChartPoint[];
}

// score=NULL (not yet evaluated) is excluded entirely — not a result yet.
// score=0.0 is exclusively a judge-call failure (judge() clamps real scores
// to [1.0, 5.0], so 0.0 only ever comes from the except branch). Plotting
// it as a normal point — even in a different color — would still occupy y=0
// and read as a quality regression. Instead it becomes a gap in the line
// (connectNulls=false) plus a labeled ReferenceLine.
function toChartData(runs: Run[]): ChartData {
  const sorted = [...runs].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const points: ChartPoint[] = [];
  const failures: ChartPoint[] = [];

  for (const run of sorted) {
    if (run.score === null) continue;

    const date = new Date(run.created_at).toLocaleDateString();
    if (run.score === 0) {
      points.push({ date, score: null, runId: run.id }); // gap
      failures.push({ date, score: 0, runId: run.id });
    } else {
      points.push({ date, score: run.score, runId: run.id });
    }
  }

  return { points, failures };
}

interface Props {
  runs: Run[];
}

export function ScoreTrendChart({ runs }: Props) {
  const { points, failures } = toChartData(runs);

  if (points.length === 0) {
    return (
      <p style={{ color: "var(--color-text-muted)", padding: "1rem 0" }}>
        No evaluated runs yet — score chart needs at least one judged run.
      </p>
    );
  }

  return (
    <div style={{ width: "100%", height: "16rem" }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--color-text-secondary)" }} />
          <YAxis domain={[1, 5]} tick={{ fontSize: 12, fill: "var(--color-text-secondary)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: `1px solid var(--color-border)`,
              borderRadius: "0.375rem",
              color: "var(--color-text-primary)",
            }}
          />
          {/* y=4.0 ship threshold — amber dashed, rendered before the Line so dots sit on top */}
          <ReferenceLine
            y={4}
            stroke="var(--color-text-warning)"
            strokeDasharray="6 3"
            label={{
              value: "Ship threshold",
              position: "insideTopRight",
              fill: "var(--color-text-warning)",
              fontSize: 11,
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--color-text-secondary)"
            strokeWidth={2}
            connectNulls={false}
            dot={(props: { cx: number; cy: number; payload: ChartPoint; index: number }) => {
              const { cx, cy, payload, index } = props;
              if (payload.score === null) return <g key={index} />;
              const fill =
                payload.score >= 4.0
                  ? "var(--color-text-success)"
                  : "var(--color-text-danger)";
              return <circle key={index} cx={cx} cy={cy} r={4} fill={fill} stroke="none" />;
            }}
            name="Judge score"
          />
          {failures.map((f) => (
            <ReferenceLine
              key={f.runId}
              x={f.date}
              stroke="var(--color-text-danger)"
              strokeDasharray="4 4"
              label={{
                value: "judge failed",
                position: "top",
                fill: "var(--color-text-danger)",
                fontSize: 10,
              }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
