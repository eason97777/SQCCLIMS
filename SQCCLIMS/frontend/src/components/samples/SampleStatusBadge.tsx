type SampleStatusBadgeProps = {
  status: string;
};

const statusClassMap: Record<string, string> = {
  待测试: "warn",
  测试中: "active",
  已完成: "done",
  已归档: "",
};

export function SampleStatusBadge({ status }: SampleStatusBadgeProps) {
  const className = statusClassMap[status] || "";

  return <span className={`tag ${className}`.trim()}>{status}</span>;
}
