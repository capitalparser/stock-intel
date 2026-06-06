import { Outlet, useRouterState } from "@tanstack/react-router";
import { DashboardSnapshot } from "../data/snapshot";
import { SnapshotExportControls } from "../export/SnapshotExportControls";
import { Header } from "./Header";
import { Tabs } from "./Tabs";

type CockpitShellProps = {
  snapshot: DashboardSnapshot;
};

export function CockpitShell({ snapshot }: CockpitShellProps) {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const currentTab =
    pathname === "/progress" ? "진행현황" : pathname === "/attention" ? "주의 필요" : pathname === "/evidence" ? "근거" : pathname === "/next-actions" ? "다음 행동" : "요약";

  return (
    <main className="min-h-screen bg-bg p-md text-text md:p-lg">
      <section
        className="mx-auto flex max-w-7xl flex-col gap-lg rounded-md border border-line bg-surface p-md shadow-sm md:p-lg"
        data-cockpit-profile="executive_cockpit"
        data-testid="cockpit-shell"
      >
        <Header snapshot={snapshot} />
        <SnapshotExportControls snapshot={snapshot} currentTab={currentTab} />
        <Tabs />
        <div className="min-h-[360px]">
          <Outlet />
        </div>
      </section>
    </main>
  );
}
