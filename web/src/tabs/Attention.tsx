import { useMemo, useState } from "react";
import { Badge } from "../components/Badges";
import { DashboardSnapshot } from "../data/snapshot";
import { AttentionCategory, attentionCategories, getAttentionCategories } from "../lib/risk";

type AttentionProps = {
  snapshot: DashboardSnapshot;
};

export function Attention({ snapshot }: AttentionProps) {
  const [active, setActive] = useState<AttentionCategory>("위험");
  const rows = useMemo(
    () =>
      snapshot.candidates
        .map((candidate) => ({ candidate, categories: getAttentionCategories(candidate) }))
        .filter((row) => row.categories.length > 0 && row.categories.includes(active)),
    [active, snapshot.candidates],
  );

  return (
    <section className="grid gap-md">
      <div className="flex flex-wrap gap-sm" aria-label="주의 필터">
        {attentionCategories.map((category) => (
          <button
            key={category}
            type="button"
            className={`rounded-sm border px-sm py-xs text-sm font-semibold ${
              active === category ? "border-info text-info" : "border-line text-textMuted"
            }`}
            onClick={() => setActive(category)}
          >
            {category}
          </button>
        ))}
      </div>
      <div className="grid gap-sm">
        {rows.map(({ candidate, categories }) => (
          <article key={candidate.ticker} className="rounded-md border border-line bg-surface p-md">
            <div className="flex flex-wrap items-start justify-between gap-sm">
              <div>
                <h3 className="text-lg font-semibold">{candidate.ticker}</h3>
                <p className="text-sm text-textMuted">{candidate.company}</p>
              </div>
              <div className="flex flex-wrap gap-xs">
                {categories.map((category) => (
                  <Badge key={category} tone={category === "위험" || category === "차단" ? "risk" : "warn"}>
                    {category}
                  </Badge>
                ))}
              </div>
            </div>
            <p className="mt-sm text-sm text-textMuted">{candidate.risk_flags.join(" · ") || candidate.bear_case[0] || "주의 사유 확인 필요"}</p>
            {candidate.independence_status ? <p className="mt-xs text-sm text-warn">독립성 확인 필요</p> : null}
          </article>
        ))}
        {rows.length === 0 ? <p className="rounded-md border border-line p-md text-sm text-textMuted">선택한 조건에 해당하는 후보가 없습니다.</p> : null}
      </div>
    </section>
  );
}
