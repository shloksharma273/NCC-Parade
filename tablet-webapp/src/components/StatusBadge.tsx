import type { SessionStatus } from "../types/session";
import { sessionStatusLabel } from "../utils/resultMapper";

const STATUS_COLORS: Record<string, string> = {
  CREATED: "bg-slate-200 text-slate-800",
  READY: "bg-blue-100 text-blue-800",
  RECORDING: "bg-red-100 text-red-800 animate-pulse",
  SAVING: "bg-amber-100 text-amber-800",
  PROCESSING: "bg-indigo-100 text-indigo-800",
  REPORT_READY: "bg-green-100 text-green-800",
  FAILED: "bg-red-200 text-red-900",
  CANCELLED: "bg-slate-300 text-slate-700",
};

type Props = {
  status: SessionStatus | string;
  large?: boolean;
};

export function StatusBadge({ status, large }: Props) {
  const color = STATUS_COLORS[status] ?? "bg-slate-200 text-slate-800";
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ${color} ${
        large ? "px-4 py-2 text-lg" : "px-3 py-1 text-sm"
      }`}
    >
      {sessionStatusLabel(status)}
    </span>
  );
}
