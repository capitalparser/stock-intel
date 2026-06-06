import { KpiStrip } from "../cockpit/KpiStrip";
import { RegimePanel } from "../components/RegimePanel";
import { DashboardSnapshot } from "../data/snapshot";

type SummaryProps = {
  snapshot: DashboardSnapshot;
};

export function Summary({ snapshot }: SummaryProps) {
  return (
    <div className="grid gap-lg">
      <RegimePanel snapshot={snapshot} />
      <KpiStrip indicators={snapshot.market_indicators} />
    </div>
  );
}
