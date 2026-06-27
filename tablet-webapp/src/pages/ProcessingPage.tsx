import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSession } from "../api/sessionApi";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { ProgressStepper } from "../components/ProgressStepper";
import { StatusBadge } from "../components/StatusBadge";
import { useSessionProgress } from "../hooks/useSessionProgress";
import { drillTypeLabel } from "../utils/resultMapper";

export function ProcessingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { progress, wsConnected } = useSessionProgress(sessionId, true);

  useEffect(() => {
    if (!sessionId) return;

    if (progress.status === "REPORT_READY") {
      navigate(`/sessions/${sessionId}/report`, { replace: true });
      return;
    }

    if (progress.status === "FAILED") {
      return;
    }

    const check = async () => {
      try {
        const session = await getSession(sessionId);
        if (session.status === "REPORT_READY") {
          navigate(`/sessions/${sessionId}/report`, { replace: true });
        }
      } catch {
        /* ignore */
      }
    };
    check();
  }, [sessionId, progress.status, navigate]);

  if (!sessionId) {
    return (
      <PageLayout title="Processing">
        <ErrorBanner message="Missing session ID." />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Analysing Drill">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-slate-500">Session ID</p>
            <p className="font-mono">{sessionId}</p>
          </div>
          <StatusBadge status={progress.status} large />
        </div>

        <p className="text-slate-600">
          {wsConnected ? "Live updates connected" : "Using polling fallback (WebSocket unavailable)"}
        </p>

        <ProgressStepper
          stage={progress.stage}
          progress={progress.progress}
          message={progress.message}
        />

        {progress.status === "FAILED" && (
          <>
            <ErrorBanner
              message={
                progress.message ||
                "Analysis failed. Please retake the drill or check camera visibility."
              }
            />
            <PrimaryButton onClick={() => navigate("/sessions/new")}>Retake Drill</PrimaryButton>
            <PrimaryButton variant="secondary" onClick={() => navigate("/dashboard")}>
              Back to Dashboard
            </PrimaryButton>
          </>
        )}

        {progress.status === "PROCESSING" && (
          <LoadingState message={`Analysing ${drillTypeLabel("kadam_tal")}...`} />
        )}
      </div>
    </PageLayout>
  );
}
