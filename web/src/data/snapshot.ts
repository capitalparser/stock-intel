import { z } from "zod";

const nullableNumber = z.number().nullable().optional();
const nullableString = z.string().nullable().optional();

export const axisReadSchema = z.object({
  dimension: z.string(),
  label: z.string(),
  state: z.string(),
  pctile: nullableNumber,
  read: z.string(),
  symbols: z.array(z.string()).default([]),
  source_kind: nullableString,
});

export const marketRegimeSchema = z.object({
  market: z.string().optional(),
  regime: z.string(),
  why_it_matters: z.string(),
  next_action: z.string(),
  axis_reads: z.array(axisReadSchema).default([]),
  data_gaps: z.array(z.string()).default([]),
});

export const transitionSchema = z.object({
  changed: z.boolean().default(false),
  to: z.string().optional(),
  from: z.string().optional(),
  from_regime: z.string().optional(),
  streak: z.number().int().nullable().optional(),
  whipsaw: z.boolean().default(false),
  axis_changes: z.array(z.string()).default([]),
});

export const dualRegimeSchema = z.object({
  as_of: z.string(),
  us: marketRegimeSchema,
  kr: marketRegimeSchema,
  transitions: z.object({
    us: transitionSchema,
    kr: transitionSchema,
  }),
});

export const marketIndicatorSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  group: z.string().optional(),
  price: nullableNumber,
  day_change_pct: nullableNumber,
  read: z.string().optional().default(""),
  series: z.array(z.number()).optional().default([]),
});

export const lensSchema = z.object({
  id: z.string(),
  kind: z.string().optional(),
  name: z.string(),
  conviction: z.string().optional(),
  direction: z.string().optional(),
  weights: z.record(z.string(), z.number()).optional().default({}),
  risks: z.array(z.string()).optional().default([]),
});

export const catalystSchema = z.object({
  type: z.string(),
  direction: z.string().optional(),
  date: z.string().optional(),
  days: z.number().nullable().optional(),
  label: z.string(),
  detail: z.string().optional().default(""),
});

export const candidateSchema = z.object({
  ticker: z.string(),
  company: z.string(),
  sector: z.string().optional().default(""),
  score: z.number().nullable().optional(),
  status: z.string().optional().default(""),
  linked_lenses: z.array(z.object({ id: z.string(), name: z.string() })).optional().default([]),
  strongest_lens: z.string().optional().default(""),
  evidence: z.array(z.string()).optional().default([]),
  gaps: z.array(z.string()).optional().default([]),
  risk_flags: z.array(z.string()).optional().default([]),
  thesis: z.string().optional().default(""),
  bull_case: z.array(z.string()).optional().default([]),
  bear_case: z.array(z.string()).optional().default([]),
  next_action: z.string().optional().default(""),
  price: nullableNumber,
  day_change_pct: nullableNumber,
  pe: nullableNumber,
  pbr: nullableNumber,
  peer_pe: nullableNumber,
  peer_group: z.string().optional().default(""),
  short_ratio: nullableNumber,
  net_flow_signal: z.string().optional(),
  independence_status: z.string().optional().default(""),
  independence_reason: z.string().optional().default(""),
  auditor: z.string().optional().default(""),
  catalysts: z.array(catalystSchema).optional().default([]),
  metrics: z
    .object({
      valuation: nullableNumber,
      quality: nullableNumber,
      growth: nullableNumber,
      revision: nullableNumber,
      momentum: nullableNumber,
    })
    .optional(),
  expectation_verdict: z.string().optional().default(""),
  data_quality: z
    .object({
      missing: z.array(z.string()).optional().default([]),
      proxy: z.array(z.string()).optional().default([]),
      errors: z.array(z.string()).optional().default([]),
      as_of: z.string().optional(),
    })
    .optional(),
  price_series: z.array(z.number()).optional().default([]),
});

export const valuationExpectationSchema = z.object({
  ticker: z.string(),
  forward_pe: nullableNumber,
  rev_growth_pct: nullableNumber,
  eps_growth_pct: nullableNumber,
  fcf_margin_pct: nullableNumber,
  verdict: z.string().optional().default(""),
  read: z.string().optional().default(""),
  data_gaps: z.array(z.string()).optional().default([]),
});

export const dashboardSnapshotSchema = z.object({
  as_of: z.string(),
  generated_at: z.string().optional(),
  price_time: z.string().optional(),
  dual_regime: dualRegimeSchema,
  market_indicators: z.array(marketIndicatorSchema).default([]),
  lenses: z.array(lensSchema).default([]),
  candidates: z.array(candidateSchema).default([]),
  valuation_expectations: z.array(valuationExpectationSchema).optional().default([]),
});

export type DashboardSnapshot = z.infer<typeof dashboardSnapshotSchema>;
export type Candidate = z.infer<typeof candidateSchema>;
export type MarketIndicator = z.infer<typeof marketIndicatorSchema>;

export function parseDashboardSnapshot(input: unknown): DashboardSnapshot {
  return dashboardSnapshotSchema.parse(input);
}

export function getSnapshotErrorMessage(input: unknown): string {
  const parsed = dashboardSnapshotSchema.safeParse(input);
  if (parsed.success) return "";
  const firstIssue = parsed.error.issues[0];
  return `상황판 데이터를 읽지 못했습니다. ${firstIssue?.path.join(".") || "root"} 항목을 확인하세요.`;
}

export async function loadDashboardSnapshot(path = "/dashboard-latest.json"): Promise<DashboardSnapshot> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`상황판 데이터를 읽지 못했습니다. HTTP ${response.status}`);
  }
  const json = await response.json();
  return parseDashboardSnapshot(json);
}
