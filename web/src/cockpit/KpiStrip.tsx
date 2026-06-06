import { MarketIndicator } from "../data/snapshot";

type KpiStripProps = {
  indicators: MarketIndicator[];
};

export function KpiStrip({ indicators }: KpiStripProps) {
  return (
    <section className="grid gap-sm md:grid-cols-4">
      {indicators.slice(0, 4).map((indicator) => (
        <article key={indicator.symbol} className="rounded-md border border-line bg-surface p-md">
          <p className="text-xs font-semibold text-textMuted">{indicator.group || indicator.symbol}</p>
          <h3 className="mt-xs text-sm font-semibold text-text">{indicator.name}</h3>
          <p className="mt-sm text-xl font-semibold">{indicator.price ?? "-"}</p>
          <p className={indicator.day_change_pct && indicator.day_change_pct < 0 ? "text-sm text-risk" : "text-sm text-ok"}>
            {indicator.day_change_pct == null ? "변동률 없음" : `${indicator.day_change_pct.toFixed(2)}%`}
          </p>
          <p className="mt-xs text-xs text-textMuted">{indicator.read}</p>
        </article>
      ))}
    </section>
  );
}
