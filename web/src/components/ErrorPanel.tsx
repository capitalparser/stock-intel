type ErrorPanelProps = {
  title?: string;
  message: string;
};

export function ErrorPanel({ title = "데이터 오류", message }: ErrorPanelProps) {
  return (
    <section className="rounded-md border border-risk bg-surface p-lg text-text" role="alert">
      <p className="text-sm font-semibold text-risk">{title}</p>
      <p className="mt-sm text-sm text-textMuted">{message}</p>
    </section>
  );
}
