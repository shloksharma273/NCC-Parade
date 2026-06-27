import type { DrillReport } from "../types/report";
import { drillTypeLabel, resultLabel } from "../utils/resultMapper";

type Props = {
  report: DrillReport;
};

export function ReportSummaryCard({ report }: Props) {
  const resultColor =
    report.result === "pass"
      ? "text-green-700"
      : report.result === "needs_correction"
        ? "text-amber-700"
        : "text-red-700";

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-sm text-slate-500">Cadet</p>
          <p className="text-xl font-semibold">{report.cadet_name}</p>
          {report.cadet_id && <p className="text-slate-600">ID: {report.cadet_id}</p>}
        </div>
        <div>
          <p className="text-sm text-slate-500">Drill</p>
          <p className="text-xl font-semibold">{drillTypeLabel(report.drill_type)}</p>
          <p className="text-slate-600">Attempt #{report.attempt_number}</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Final Score</p>
          <p className="text-3xl font-bold">{report.score} / 100</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-4">
          <p className="text-sm text-slate-500">Result</p>
          <p className={`text-3xl font-bold ${resultColor}`}>{resultLabel(report.result)}</p>
        </div>
      </div>

      {report.kadam_tal_count != null && (
        <p className="mt-4 text-slate-600">
          Kadam tal count: {report.kadam_tal_count}
          {report.average_score_per_kadam_tal != null &&
            ` · Avg ${report.average_score_per_kadam_tal.toFixed(2)}/10 per rep`}
        </p>
      )}

      {report.summary.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 font-semibold">Main Feedback</p>
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
