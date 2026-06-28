import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getAttempts } from "../api/decisionApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { resultLabel, drillTypeLabel } from "../utils/resultMapper";

export function AttemptHistoryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [attempts, setAttempts] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) return;
    getAttempts(sessionId)
      .then((data) => setAttempts(data.attempts))
      .catch((err) => setError(parseApiError(err)))
      .finally(() => setLoading(false));
  }, [sessionId]);

  return (
    <PageLayout title="Attempt History" strip="Review Mode" backTo={`/sessions/${sessionId}/report`}>
      {loading && <LoadingState />}
      {error && <ErrorBanner message={error} />}
      {!loading && attempts.length === 0 && <p className="text-slate-600">No prior attempts found.</p>}
      <div className="space-y-3">
        {attempts.map((attempt) => {
          const id = String(attempt.session_id);
          return (
            <button
              key={id}
              type="button"
              onClick={() => navigate(`/sessions/${id}/report`)}
              className="command-card flex w-full items-center justify-between p-4 text-left hover:bg-[var(--color-sand)]"
            >
              <div>
                <p className="font-bold">Attempt #{String(attempt.attempt_number)}</p>
                <p className="text-sm text-slate-600">{drillTypeLabel(String(attempt.drill_type))}</p>
              </div>
              <div className="text-right">
                <p className="font-bold tabular-nums">{attempt.score != null ? `${attempt.score}/100` : "—"}</p>
                <p className="text-sm">{attempt.final_result || attempt.result ? resultLabel(String(attempt.final_result || attempt.result)) : "—"}</p>
              </div>
            </button>
          );
        })}
      </div>
    </PageLayout>
  );
}
