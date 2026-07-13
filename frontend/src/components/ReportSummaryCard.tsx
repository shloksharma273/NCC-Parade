import type { DrillReport } from "../types/report";
import { drillTypeLabel, resultLabel } from "../utils/resultMapper";
import { formatDateTime } from "../utils/formatTime";
import { resultStyles } from "../theme/statusStyles";

type Props = {
  report: DrillReport;
};

export function ReportSummaryCard({ report }: Props) {
  const displayResult = report.final_result ?? report.result;
  const style = resultStyles[displayResult] ?? resultStyles.fail;
  const aiResult = report.ai_result ?? report.result;

  return (
    <div className="command-card overflow-hidden">
      <div className="rank-strip px-4 py-2">Session Summary</div>
      <div className="grid gap-4 p-6 md:grid-cols-2">
        <div>
          <p className="text-sm text-slate-500">Cadet</p>
          <p className="text-xl font-semibold">{report.cadet_name}</p>
          {report.cadet_id && <p className="text-slate-600">ID: {report.cadet_id}</p>}
          {(report.squad || report.unit) && (
            <p className="text-sm text-slate-600">
              {[report.squad, report.unit].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        <div>
          <p className="text-sm text-slate-500">Drill</p>
          <p className="text-xl font-semibold">{drillTypeLabel(report.drill_type)}</p>
          <p className="text-slate-600">Attempt #{report.attempt_number}</p>
        </div>
      </div>

      <div className="mx-6 mb-6 grid gap-3 sm:grid-cols-2">
        <div className={`rounded-xl border-2 p-4 ${style.border} ${style.bg}`}>
          <p className="text-sm opacity-80">Final Decision</p>
          <p className={`font-command text-3xl font-bold uppercase ${style.text}`}>
            {resultLabel(displayResult)}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{report.score} / 100</p>
        </div>
        <div className="rounded-xl border-2 border-[var(--color-khaki)] bg-[var(--color-sand)] p-4">
          <p className="text-sm text-slate-600">AI Result</p>
          <p className="font-command text-2xl font-bold">{resultLabel(aiResult)}</p>
          {report.instructor_decision && (
            <p className="mt-2 text-sm text-slate-600">
              Instructor override: {resultLabel(report.instructor_decision)}
            </p>
          )}
        </div>
      </div>

      {report.instructor_remarks && (
        <div className="mx-6 mb-4 rounded-xl bg-[var(--color-sand)] px-4 py-3 text-sm">
          <span className="font-semibold">Instructor remarks: </span>
          {report.instructor_remarks}
        </div>
      )}

      <div className="mx-6 mb-6 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <p className="text-slate-500">Session ID</p>
          <p className="font-mono">{report.session_id}</p>
        </div>
        <div>
          <p className="text-slate-500">Report Generated</p>
          <p>{formatDateTime(report.created_at)}</p>
        </div>
      </div>

      {report.kadam_tal_count != null && (
        <p className="mx-6 mb-4 text-slate-600">
          Kadam tal count: {report.kadam_tal_count}
          {report.average_score_per_kadam_tal != null &&
            ` · Avg ${report.average_score_per_kadam_tal.toFixed(2)}/10 per rep`}
        </p>
      )}

      {report.summary.length > 0 && (
        <div className="border-t border-[var(--color-khaki)] px-6 py-5">
          <p className="mb-2 font-command text-lg font-bold">Main Feedback</p>
          <ol className="list-decimal space-y-2 pl-5 text-slate-700">
            {report.summary.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
