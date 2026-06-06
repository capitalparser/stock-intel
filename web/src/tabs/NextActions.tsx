import { DashboardSnapshot } from "../data/snapshot";

type NextActionsProps = {
  snapshot: DashboardSnapshot;
};

export function NextActions({ snapshot }: NextActionsProps) {
  const candidates = snapshot.candidates.filter((candidate) => candidate.next_action).slice(0, 30);

  return (
    <section className="grid gap-lg lg:grid-cols-[1fr_1fr]">
      <div className="rounded-md border border-line bg-surface p-md">
        <h2 className="text-lg font-semibold">후보별 다음 행동</h2>
        <div className="mt-md grid gap-sm">
          {candidates.map((candidate) => (
            <article key={candidate.ticker} className="rounded-sm border border-line bg-surfaceAlt p-sm">
              <p className="text-sm font-semibold">{candidate.ticker}</p>
              <p className="mt-xs text-sm text-textMuted">{candidate.next_action}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="rounded-md border border-line bg-surface p-md">
        <h2 className="text-lg font-semibold">국면 다음 행동</h2>
        <div className="mt-md grid gap-sm">
          <article className="rounded-sm border border-line bg-surfaceAlt p-sm">
            <p className="text-sm font-semibold">미국</p>
            <p className="mt-xs text-sm text-textMuted">{snapshot.dual_regime.us.next_action}</p>
          </article>
          <article className="rounded-sm border border-line bg-surfaceAlt p-sm">
            <p className="text-sm font-semibold">한국</p>
            <p className="mt-xs text-sm text-textMuted">{snapshot.dual_regime.kr.next_action}</p>
          </article>
        </div>
      </div>
    </section>
  );
}
