import type { ReadinessCheck } from "../api/readinessApi";
import { checkStatusIcon } from "../theme/statusStyles";

type Props = {
  checks: ReadinessCheck[];
};

const STATUS_COLOR: Record<string, string> = {
  pass: "text-[var(--color-success)]",
  warning: "text-[var(--color-warning)]",
  fail: "text-[var(--color-fail)]",
};

export function ReadinessChecklist({ checks }: Props) {
  return (
    <ul className="space-y-3">
      {checks.map((check) => (
        <li
          key={check.key}
          className="flex items-start gap-3 rounded-xl border border-[var(--color-khaki)] bg-white px-4 py-3"
        >
          <span className={`text-xl font-bold ${STATUS_COLOR[check.status]}`}>
            {checkStatusIcon[check.status]}
          </span>
          <div>
            <p className="font-semibold">{check.name}</p>
            <p className="text-sm text-slate-600">{check.message}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
