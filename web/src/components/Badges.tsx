type BadgeProps = {
  tone?: "neutral" | "ok" | "warn" | "risk" | "info";
  children: React.ReactNode;
};

const toneClass = {
  neutral: "border-line bg-surfaceAlt text-textMuted",
  ok: "border-ok bg-surface text-ok",
  warn: "border-warn bg-surface text-warn",
  risk: "border-risk bg-surface text-risk",
  info: "border-info bg-surface text-info",
};

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={`inline-flex rounded-sm border px-sm py-xs text-xs font-semibold ${toneClass[tone]}`}>{children}</span>;
}
