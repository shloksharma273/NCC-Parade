import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchReadyReport } from "../api/reportApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { ParameterTable } from "../components/ParameterTable";
import { PrimaryButton } from "../components/PrimaryButton";
import { getBackendUrl, mediaUrl } from "../utils/backendUrl";
import type { DrillReport } from "../types/report";
import { drillTypeLabel, resultLabel } from "../utils/resultMapper";

export function DetailedReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<DrillReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    fetchReadyReport(sessionId)
      .then(setReport)
      .catch((err) => setError(parseApiError(err)))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <PageLayout title="Detailed Report"><LoadingState /></PageLayout>;
  if (error || !report) {
    return (
      <PageLayout title="Detailed Report" backTo={`/sessions/${sessionId}/report`}>
        <ErrorBanner message={error ?? "Report unavailable"} />
      </PageLayout>
    );
  }

  const backend = getBackendUrl() ?? "";
  const keyFrame = mediaUrl(backend, report.media?.key_frame_url);

  return (
    <PageLayout
      title="Detailed Report"
      strip="Review Mode"
      subtitle={`${report.cadet_name} · ${drillTypeLabel(report.drill_type)}`}
      backTo={`/sessions/${sessionId}/report`}
    >
      <div className="space-y-6">
        <div className="command-card grid gap-4 p-6 md:grid-cols-2">
          <div>
            <p className="text-sm text-slate-500">AI Result</p>
            <p className="text-xl font-bold">{resultLabel(report.ai_result ?? report.result)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Final Decision</p>
            <p className="text-xl font-bold">{resultLabel(report.final_result ?? report.result)}</p>
          </div>
        </div>
        <ParameterTable parameters={report.parameters} />
        {keyFrame && (
          <div className="command-card p-6">
            <h2 className="mb-4 font-command text-xl font-bold">Evidence — Key Frame</h2>
            <img src={keyFrame} alt="Key drill frame" className="max-h-96 rounded-xl border-2 border-[var(--color-khaki)]" />
          </div>
        )}
        <PrimaryButton variant="secondary" onClick={() => navigate(`/sessions/${sessionId}/attempts`)}>
          View Attempt History
        </PrimaryButton>
      </div>
    </PageLayout>
  );
}
