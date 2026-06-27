import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchReadyReport } from "../api/reportApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { ParameterTable } from "../components/ParameterTable";
import { PrimaryButton } from "../components/PrimaryButton";
import { ReportSummaryCard } from "../components/ReportSummaryCard";
import { useSessionState } from "../hooks/useSessionState";
import { getBackendUrl, mediaUrl } from "../utils/backendUrl";
import type { DrillReport } from "../types/report";

export function ReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { setRetakeContext } = useSessionState();

  const [report, setReport] = useState<DrillReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReadyReport(sessionId);
      setReport(data);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRetake = () => {
    if (!report) return;
    setRetakeContext({
      cadet_id: report.cadet_id ?? undefined,
      cadet_name: report.cadet_name,
      drill_type: report.drill_type,
      camera_id: "0",
    });
    navigate("/sessions/new");
  };

  if (loading) {
    return (
      <PageLayout title="Report">
        <LoadingState message="Loading report..." />
      </PageLayout>
    );
  }

  if (error || !report) {
    return (
      <PageLayout title="Report" backTo="/dashboard">
        <ErrorBanner message={error ?? "Report not available."} />
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <PrimaryButton onClick={load}>Retry</PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/dashboard")}>
            Back to Dashboard
          </PrimaryButton>
        </div>
      </PageLayout>
    );
  }

  const backend = getBackendUrl() ?? "";
  const keyFrame = mediaUrl(backend, report.media?.key_frame_url);
  const rawVideo = mediaUrl(backend, report.media?.raw_video_url);
  const annotatedVideo = mediaUrl(backend, report.media?.annotated_video_url);

  return (
    <PageLayout title="Drill Report" backTo="/dashboard">
      <div className="space-y-6">
        <ReportSummaryCard report={report} />

        <div>
          <h2 className="mb-3 text-xl font-bold">Parameter Scores</h2>
          <ParameterTable parameters={report.parameters} />
        </div>

        {(keyFrame || rawVideo || annotatedVideo) && (
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <h2 className="mb-4 text-xl font-bold">Media</h2>
            {keyFrame && (
              <div className="mb-4">
                <p className="mb-2 font-semibold">Key Frame</p>
                <img src={keyFrame} alt="Key drill frame" className="max-h-80 rounded-xl border" />
              </div>
            )}
            <div className="flex flex-wrap gap-4">
              {rawVideo && (
                <a href={rawVideo} target="_blank" rel="noreferrer" className="text-blue-700 underline">
                  Raw Video
                </a>
              )}
              {annotatedVideo && (
                <a href={annotatedVideo} target="_blank" rel="noreferrer" className="text-blue-700 underline">
                  Annotated Video
                </a>
              )}
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <PrimaryButton onClick={handleRetake}>Retake Same Drill</PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/sessions/new")}>
            New Session
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/dashboard")}>
            Back to Dashboard
          </PrimaryButton>
        </div>
      </div>
    </PageLayout>
  );
}
