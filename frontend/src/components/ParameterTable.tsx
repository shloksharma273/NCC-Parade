import type { DrillParameter } from "../types/report";
import { parameterStatusLabel } from "../utils/resultMapper";

type Props = {
  parameters: DrillParameter[];
};

const STATUS_COLORS: Record<string, string> = {
  pass: "text-green-700",
  correct: "text-green-700",
  needs_correction: "text-amber-700",
  fail: "text-red-700",
  incorrect: "text-red-700",
};

export function ParameterTable({ parameters }: Props) {
  if (parameters.length === 0) {
    return <p className="text-slate-600">No parameter data available.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-800 text-white">
          <tr>
            <th className="px-4 py-3 font-semibold">Parameter</th>
            <th className="px-4 py-3 font-semibold">Expected</th>
            <th className="px-4 py-3 font-semibold">Actual</th>
            <th className="px-4 py-3 font-semibold">Score</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Feedback</th>
          </tr>
        </thead>
        <tbody>
          {parameters.map((param) => (
            <tr key={param.name} className="border-t border-slate-100 even:bg-slate-50">
              <td className="px-4 py-4 font-medium">{param.name}</td>
              <td className="px-4 py-4">{param.expected}</td>
              <td className="px-4 py-4">{param.actual}</td>
              <td className="px-4 py-4">{(param.score * 10).toFixed(1)}/10</td>
              <td className={`px-4 py-4 font-semibold ${STATUS_COLORS[param.status] ?? ""}`}>
                {parameterStatusLabel(param.status)}
              </td>
              <td className="px-4 py-4 text-slate-600">{param.feedback ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
