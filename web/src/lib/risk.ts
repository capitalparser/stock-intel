import { Candidate } from "../data/snapshot";

export type AttentionCategory = "차단" | "과열" | "위험" | "공매도" | "데이터부족";

export const attentionCategories: AttentionCategory[] = ["차단", "과열", "위험", "공매도", "데이터부족"];

export function getAttentionCategories(candidate: Candidate): AttentionCategory[] {
  const text = [
    candidate.status,
    candidate.independence_status,
    candidate.expectation_verdict,
    ...candidate.risk_flags,
    ...candidate.gaps,
    ...(candidate.data_quality?.missing ?? []),
    ...(candidate.data_quality?.errors ?? []),
  ]
    .join(" ")
    .toLowerCase();

  const categories = new Set<AttentionCategory>();
  if (text.includes("block") || text.includes("차단")) categories.add("차단");
  if ((candidate.pe ?? 0) > 45 || text.includes("과열") || text.includes("overheat")) categories.add("과열");
  if (text.includes("위험") || text.includes("risk") || text.includes("확인 필요")) categories.add("위험");
  if ((candidate.short_ratio ?? 0) > 5 || text.includes("공매도") || text.includes("short")) categories.add("공매도");
  if (candidate.gaps.length > 0 || (candidate.data_quality?.missing?.length ?? 0) > 0 || text.includes("데이터")) categories.add("데이터부족");
  return [...categories];
}
