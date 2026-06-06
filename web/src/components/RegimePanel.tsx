import { DashboardSnapshot } from "../data/snapshot";
import { Badge } from "./Badges";

type RegimePanelProps = {
  snapshot: DashboardSnapshot;
};

function pctileLabel(value?: number | null) {
  if (value == null) return "-";
  return `${Math.round(value * 100)}%`;
}

function transitionLabel(transition: DashboardSnapshot["dual_regime"]["transitions"]["us"]) {
  if (transition.changed) return "전환";
  return "유지";
}

export function RegimePanel({ snapshot }: RegimePanelProps) {
  const regimes = [
    { label: "미국 국면", regime: snapshot.dual_regime.us, transition: snapshot.dual_regime.transitions.us },
    { label: "한국 국면", regime: snapshot.dual_regime.kr, transition: snapshot.dual_regime.transitions.kr },
  ];

  return (
    <section className="grid gap-md lg:grid-cols-2">
      {regimes.map((item) => (
        <article key={item.label} className="rounded-md border border-line bg-surface p-md">
          <div className="flex flex-wrap items-center justify-between gap-sm">
            <div>
              <p className="text-sm font-semibold text-info">{item.label}</p>
              <h2 className="mt-xs text-2xl font-semibold">{item.regime.regime}</h2>
            </div>
            <div className="flex flex-wrap gap-xs">
              <Badge tone={item.transition.changed ? "warn" : "ok"}>{transitionLabel(item.transition)}</Badge>
              <Badge tone="info">{item.transition.streak ?? 0}일 연속</Badge>
              <Badge tone={item.transition.whipsaw ? "risk" : "neutral"}>{item.transition.whipsaw ? "whipsaw" : "안정"}</Badge>
            </div>
          </div>
          <p className="mt-sm text-sm text-textMuted">{item.regime.why_it_matters}</p>
          <div className="mt-md grid gap-sm">
            {item.regime.axis_reads.map((axis) => (
              <div key={`${item.label}-${axis.dimension}`} className="rounded-sm border border-line bg-surfaceAlt p-sm">
                <div className="flex items-center justify-between gap-sm">
                  <span className="text-sm font-semibold">{axis.label}</span>
                  <span className="text-sm font-semibold text-info">{pctileLabel(axis.pctile)}</span>
                </div>
                <p className="mt-xs text-xs text-textMuted">{axis.read}</p>
              </div>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
