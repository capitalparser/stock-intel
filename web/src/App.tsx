import { useEffect, useState } from "react";
import { ErrorPanel } from "./components/ErrorPanel";
import { CockpitApp } from "./cockpit/CockpitApp";
import { DashboardSnapshot, getSnapshotErrorMessage, loadDashboardSnapshot } from "./data/snapshot";

type SnapshotState =
  | { status: "loading" }
  | { status: "ready"; snapshot: DashboardSnapshot }
  | { status: "error"; message: string };

export function App() {
  const [snapshotState, setSnapshotState] = useState<SnapshotState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    loadDashboardSnapshot()
      .then((snapshot) => {
        if (active) setSnapshotState({ status: "ready", snapshot });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setSnapshotState({
          status: "error",
          message: error instanceof Error ? error.message : getSnapshotErrorMessage(error),
        });
      });

    return () => {
      active = false;
    };
  }, []);

  if (snapshotState.status === "ready") {
    return <CockpitApp snapshot={snapshotState.snapshot} />;
  }

  return (
    <main className="min-h-screen bg-bg p-lg text-text">
      <section className="mx-auto max-w-6xl rounded-md border border-line bg-surface p-lg">
        <p className="text-sm text-textMuted">개인 투자 상황판</p>
        <h1 className="mt-sm text-2xl font-semibold">Lane B React Cockpit</h1>
        {snapshotState.status === "loading" ? <p className="mt-md text-sm text-textMuted">상황판 데이터를 준비하고 있습니다.</p> : null}
        {snapshotState.status === "error" ? <ErrorPanel message={snapshotState.message} /> : null}
      </section>
    </main>
  );
}
