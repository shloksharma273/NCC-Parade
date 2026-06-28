import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchReadyReport, getReportPdfDownloadUrl } from "../api/reportApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { ReportSummaryCard } from "../components/ReportSummaryCard";
import { ScoreCard } from "../components/ScoreCard";
import { useSessionState } from "../hooks/useSessionState";
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
      <PageLayout title="Report" strip="Review Mode">
        <LoadingState message="Loading report..." />
      </PageLayout>
    );
  }

  if (error || !report) {
    return (
      <PageLayout title="Report" strip="Review Mode" backTo="/dashboard">
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

  const pdfDownloadUrl = getReportPdfDownloadUrl(report.session_id);
  const pdfFilename = report.media?.report_pdf_filename ?? `${report.cadet_name.replace(/\s+/g, "_")}_report.pdf`;
  const hasPdf = Boolean(report.media?.report_pdf_url || pdfDownloadUrl);
  const displayResult = report.final_result ?? report.result;

  return (
    <PageLayout title="Drill Report" strip="Review Mode" backTo="/dashboard">
      <div className="space-y-6">
        <ScoreCard result={displayResult} score={report.score} summary={report.summary} />
        <ReportSummaryCard report={report} />

        <div className="grid gap-4 sm:grid-cols-2">
          <PrimaryButton onClick={() => navigate(`/sessions/${sessionId}/report/detailed`)}>
            View Detailed Report
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate(`/sessions/${sessionId}/decision`)}>
            Manual Decision
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate(`/sessions/${sessionId}/attempts`)}>
            Attempt History
          </PrimaryButton>
          {hasPdf && pdfDownloadUrl && (
            <a href={pdfDownloadUrl} download={pdfFilename} className="block">
              <PrimaryButton variant="secondary">Save PDF Report</PrimaryButton>
            </a>
          )}
          <PrimaryButton onClick={handleRetake}>Retake Same Drill</PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/sessions/new")}>
            New Drill
          </PrimaryButton>
        </div>
      </div>
    </PageLayout>
  );
}
