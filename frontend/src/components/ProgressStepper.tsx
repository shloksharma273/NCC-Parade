import { STAGE_LABELS } from "../utils/resultMapper";

type Props = {
  stage: string;
  progress: number;
  message: string;
};

const STAGE_ORDER = [
  "video_saved",
  "pose_extraction",
  "parameter_calculation",
  "ground_truth_comparison",
  "report_generation",
  "completed",
];

function stageIcon(done: boolean, active: boolean): string {
  if (done) return "✓";
  if (active) return "⏳";
  return "○";
}

export function ProgressStepper({ stage, progress, message }: Props) {
  const currentIndex = STAGE_ORDER.indexOf(stage);

  return (
    <div className="command-card p-6">
      <div className="rank-strip mb-4 inline-block">Analysis Progress</div>
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold">{STAGE_LABELS[stage] ?? stage}</span>
          <span className="font-bold tabular-nums">{progress}%</span>
        </div>
        <div className="h-4 overflow-hidden rounded-full bg-[var(--color-sand)]">
          <div
            className="h-full rounded-full bg-[var(--color-army-green)] transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      </div>

      <p className="mb-6 text-base text-slate-700">{message}</p>

      <ul className="space-y-2">
        {STAGE_ORDER.filter((s) => s !== "completed").map((step, index) => {
          const done = currentIndex > index || stage === "completed";
          const active = step === stage;
          return (
            <li
              key={step}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-base ${
                done
                  ? "bg-green-50 text-[var(--color-success)]"
                  : active
                    ? "bg-[var(--color-sand)] font-semibold text-[var(--color-deep-olive)]"
                    : "bg-white text-slate-400"
              }`}
            >
              <span className="text-xl">{stageIcon(done, active)}</span>
              {STAGE_LABELS[step] ?? step}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
