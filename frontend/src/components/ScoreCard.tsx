import { resultLabel } from "../utils/resultMapper";
import { resultStyles } from "../theme/statusStyles";

type Props = {
  result: string;
  score: number;
  summary?: string[];
};

export function ScoreCard({ result, score, summary }: Props) {
  const style = resultStyles[result] ?? resultStyles.fail;
  return (
    <div className={`command-card overflow-hidden border-4 ${style.border}`}>
      <div className={`px-6 py-8 text-center ${style.bg} ${style.text}`}>
        <p className="rank-strip inline-block mb-3 bg-black/20 text-inherit">Final Assessment</p>
        <p className="font-command text-5xl font-bold uppercase tracking-wide">{resultLabel(result)}</p>
        <p className="mt-2 text-3xl font-bold tabular-nums">{score} / 100</p>
      </div>
      {summary && summary.length > 0 && (
        <div className="px-6 py-5">
          <p className="mb-2 font-command text-lg font-bold">Top Corrections</p>
          <ol className="list-decimal space-y-2 pl-5 text-slate-700">
            {summary.slice(0, 3).map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
