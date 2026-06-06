import { useState } from "react";
import { Inspector } from "../components/Inspector";
import { DashboardSnapshot } from "../data/snapshot";

type EvidenceProps = {
  snapshot: DashboardSnapshot;
};

export function Evidence({ snapshot }: EvidenceProps) {
  const [selectedTicker, setSelectedTicker] = useState(snapshot.candidates[0]?.ticker ?? "");
  const selected = snapshot.candidates.find((candidate) => candidate.ticker === selectedTicker) ?? snapshot.candidates[0];

  if (!selected) {
    return <p className="rounded-md border border-line p-md text-sm text-textMuted">표시할 후보가 없습니다.</p>;
  }

  return (
    <section className="grid gap-md lg:grid-cols-[260px_1fr]">
      <aside className="rounded-md border border-line bg-surface p-sm">
        {snapshot.candidates.slice(0, 20).map((candidate) => (
          <button
            key={candidate.ticker}
            type="button"
            className={`block w-full rounded-sm px-sm py-sm text-left text-sm ${
              candidate.ticker === selected.ticker ? "bg-accentSoft text-text" : "text-textMuted"
            }`}
            onClick={() => setSelectedTicker(candidate.ticker)}
          >
            {candidate.ticker}
          </button>
        ))}
      </aside>
      <Inspector candidate={selected} snapshot={snapshot} />
    </section>
  );
}
