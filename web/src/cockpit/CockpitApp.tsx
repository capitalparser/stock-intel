import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { useMemo } from "react";
import { DashboardSnapshot } from "../data/snapshot";
import { Attention } from "../tabs/Attention";
import { Evidence } from "../tabs/Evidence";
import { NextActions } from "../tabs/NextActions";
import { Progress } from "../tabs/Progress";
import { Summary } from "../tabs/Summary";
import { CockpitShell } from "./Shell";

type CockpitAppProps = {
  snapshot: DashboardSnapshot;
};

function createCockpitRouter(snapshot: DashboardSnapshot) {
  const rootRoute = createRootRoute({
    component: () => <CockpitShell snapshot={snapshot} />,
  });

  const summaryRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => <Summary snapshot={snapshot} />,
  });

  const progressRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/progress",
    component: () => <Progress snapshot={snapshot} />,
  });

  const attentionRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/attention",
    component: () => <Attention snapshot={snapshot} />,
  });

  const evidenceRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/evidence",
    component: () => <Evidence snapshot={snapshot} />,
  });

  const nextActionsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/next-actions",
    component: () => <NextActions snapshot={snapshot} />,
  });

  const routeTree = rootRoute.addChildren([summaryRoute, progressRoute, attentionRoute, evidenceRoute, nextActionsRoute]);

  return createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
}

export function CockpitApp({ snapshot }: CockpitAppProps) {
  const router = useMemo(() => createCockpitRouter(snapshot), [snapshot]);

  return <RouterProvider router={router} />;
}
