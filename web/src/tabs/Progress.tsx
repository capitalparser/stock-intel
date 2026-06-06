import { CandidateTable } from "../components/CandidateTable";
import { DashboardSnapshot } from "../data/snapshot";

type ProgressProps = {
  snapshot: DashboardSnapshot;
};

export function Progress({ snapshot }: ProgressProps) {
  return <CandidateTable candidates={snapshot.candidates} />;
}
