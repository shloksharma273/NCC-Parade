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

export function ProgressStepper({ stage, progress, message }: Props) {
  const currentIndex = STAGE_ORDER.indexOf(stage);

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between text-sm text-slate-600">
          <span>{STAGE_LABELS[stage] ?? stage}</span>
          <span className="font-semibold">{progress}%</span>
        </div>
        <div className="h-4 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-indigo-600 transition-all duration-500"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      </div>

      <p className="mb-6 text-base text-slate-700">{message}</p>

      <div className="grid gap-2 sm:grid-cols-2">
        {STAGE_ORDER.filter((s) => s !== "completed").map((step, index) => {
          const done = currentIndex > index || stage === "completed";
          const active = step === stage;
          return (
            <div
              key={step}
              className={`rounded-lg px-3 py-2 text-sm ${
                done
                  ? "bg-green-50 text-green-800"
                  : active
                    ? "bg-indigo-50 font-semibold text-indigo-800"
                    : "bg-slate-50 text-slate-500"
              }`}
            >
              {STAGE_LABELS[step] ?? step}
            </div>
          );
        })}
      </div>
    </div>
  );
}
