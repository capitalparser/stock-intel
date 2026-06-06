import { Line, LineChart, ResponsiveContainer } from "recharts";
import { pasTokens } from "../../../../00_personal_agent_system/design-kit/typescript/src/tokens";

type SparklineProps = {
  label: string;
  values?: number[];
};

export function Sparkline({ label, values = [] }: SparklineProps) {
  if (values.length === 0) return null;

  const data = values.map((value, index) => ({ index, value }));

  return (
    <div className="h-10 w-28" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line type="monotone" dataKey="value" stroke={pasTokens.color.info} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
