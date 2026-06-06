import { Candidate, DashboardSnapshot } from "../data/snapshot";

type InspectorProps = {
  candidate: Candidate;
  snapshot: DashboardSnapshot;
};

const axisLabels: Array<[key: keyof NonNullable<Candidate["metrics"]>, label: string]> = [
  ["valuation", "밸류에이션"],
  ["quality", "품질"],
  ["growth", "성장"],
  ["revision", "이익상향"],
  ["momentum", "모멘텀"],
];

function valueLabel(value?: number | null) {
  return value == null ? "확인 필요" : value.toFixed(1);
}

export function Inspector({ candidate, snapshot }: InspectorProps) {
  const valuation = snapshot.valuation_expectations.find((item) => item.ticker === candidate.ticker);

  return (
    <article className="grid gap-md rounded-md border border-line bg-surface p-md">
      <div>
        <h2 className="text-2xl font-semibold">{candidate.ticker} 근거</h2>
        <p className="mt-xs text-sm text-textMuted">{candidate.thesis}</p>
      </div>

      <section className="grid gap-sm md:grid-cols-5" aria-label="5축">
        {axisLabels.map(([key, label]) => (
          <div key={key} className="rounded-sm border border-line bg-surfaceAlt p-sm">
            <p className="text-xs font-semibold text-textMuted">{label}</p>
            <p className="mt-xs text-lg font-semibold">{valueLabel(candidate.metrics?.[key])}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-md md:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">독립성</h3>
          <p className="mt-xs text-sm text-textMuted">{candidate.independence_reason || candidate.independence_status || "확인된 제한 없음"}</p>
          <p className="mt-xs text-sm text-textMuted">감사인: {candidate.auditor || "원천 확인 필요"}</p>
        </div>
        <div>
          <h3 className="text-sm font-semibold">catalyst</h3>
          <ul className="mt-xs list-disc pl-md text-sm text-textMuted">
            {candidate.catalysts.length > 0 ? (
              candidate.catalysts.map((item) => <li key={`${item.type}-${item.label}`}>{item.label}</li>)
            ) : (
              <li>확정 catalyst 없음</li>
            )}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold">밸류에이션 기대치</h3>
          <p className="mt-xs text-sm text-textMuted">{valuation?.read || candidate.expectation_verdict || `PER ${valueLabel(candidate.pe)}`}</p>
        </div>
        <div>
          <h3 className="text-sm font-semibold">gaps</h3>
          <p className="mt-xs text-sm text-textMuted">{candidate.gaps.length > 0 ? candidate.gaps.join(" · ") : "미해결 갭 없음"}</p>
        </div>
      </section>

      <details className="rounded-sm border border-line bg-surfaceAlt p-sm">
        <summary className="cursor-pointer font-semibold">기술 세부정보</summary>
        <pre className="mt-sm overflow-x-auto text-xs text-textMuted">{JSON.stringify(candidate, null, 2)}</pre>
      </details>
    </article>
  );
}
