interface StatusMessageProps {
  tone: "info" | "success" | "error" | "empty";
  title: string;
  detail?: string;
}

export function StatusMessage({ tone, title, detail }: StatusMessageProps) {
  return (
    <div
      className={`status status-${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
    </div>
  );
}
