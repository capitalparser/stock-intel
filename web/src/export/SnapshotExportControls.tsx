import { Download } from "lucide-react";
import { DashboardSnapshot } from "../data/snapshot";
import { exportSnapshot } from "./snapshotExport";

type SnapshotExportControlsProps = {
  snapshot: DashboardSnapshot;
  currentTab: "요약" | "진행현황" | "주의 필요" | "근거" | "다음 행동";
};

function downloadHtml(filename: string, html: string) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function SnapshotExportControls({ snapshot, currentTab }: SnapshotExportControlsProps) {
  const exportWithScope = (scope: "current_tab" | "all_tabs") => {
    const html = exportSnapshot({
      scope,
      currentTab,
      snapshot,
      generatedAt: new Date(),
      source: { dashboardName: "개인 투자 상황판", userOrService: "04_stock_intel" },
      dataWindow: { from: snapshot.as_of, to: snapshot.price_time ?? snapshot.generated_at ?? snapshot.as_of },
    });
    downloadHtml(`stock-intel-${scope}-${snapshot.as_of}.html`, html);
  };

  return (
    <div className="flex flex-wrap gap-sm">
      <button className="inline-flex items-center gap-xs rounded-sm border border-line px-sm py-xs text-sm font-semibold" type="button" onClick={() => exportWithScope("current_tab")}>
        <Download size={16} /> 현재 뷰
      </button>
      <button className="inline-flex items-center gap-xs rounded-sm border border-line px-sm py-xs text-sm font-semibold" type="button" onClick={() => exportWithScope("all_tabs")}>
        <Download size={16} /> 전체
      </button>
    </div>
  );
}
