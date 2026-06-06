import { Link } from "@tanstack/react-router";
import { commonCockpitTabs } from "../../../../00_personal_agent_system/design-kit/typescript/src/cockpitProfiles";

const tabRoutes: Record<(typeof commonCockpitTabs)[number], string> = {
  요약: "/",
  진행현황: "/progress",
  "주의 필요": "/attention",
  근거: "/evidence",
  "다음 행동": "/next-actions",
};

export function Tabs() {
  return (
    <nav aria-label="상황판 탭" className="flex flex-wrap gap-sm border-b border-line">
      {commonCockpitTabs.map((tab) => (
        <Link
          key={tab}
          to={tabRoutes[tab]}
          activeOptions={{ exact: true }}
          activeProps={{ "aria-current": "page", className: "border-info text-text" }}
          inactiveProps={{ className: "border-transparent text-textMuted" }}
          className="border-b-2 px-sm py-sm text-sm font-semibold"
        >
          {tab}
        </Link>
      ))}
    </nav>
  );
}
