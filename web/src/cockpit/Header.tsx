import { DashboardSnapshot } from "../data/snapshot";

type HeaderProps = {
  snapshot: DashboardSnapshot;
};

export function Header({ snapshot }: HeaderProps) {
  const us = snapshot.dual_regime.us;
  const kr = snapshot.dual_regime.kr;

  return (
    <header className="grid gap-md border-b border-line pb-lg md:grid-cols-[1.2fr_1fr_1fr]">
      <div>
        <p className="text-sm font-semibold text-info">현재 상태</p>
        <h1 className="mt-xs text-3xl font-semibold text-text">개인 투자 상황판</h1>
        <p className="mt-sm text-sm text-textMuted">
          미국 {us.regime} · 한국 {kr.regime} · 기준일 {snapshot.as_of}
        </p>
      </div>
      <div>
        <p className="text-sm font-semibold text-info">왜 중요한가</p>
        <p className="mt-xs text-sm text-textMuted">{us.why_it_matters}</p>
        <p className="mt-xs text-sm text-textMuted">{kr.why_it_matters}</p>
      </div>
      <div>
        <p className="text-sm font-semibold text-info">다음 행동</p>
        <p className="mt-xs text-sm text-textMuted">미국: {us.next_action}</p>
        <p className="mt-xs text-sm text-textMuted">한국: {kr.next_action}</p>
      </div>
    </header>
  );
}
