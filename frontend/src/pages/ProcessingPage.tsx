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
import { useState } from "react";
import type { Session } from "../types/session";

export function ProcessingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { progress, wsConnected } = useSessionProgress(sessionId, true);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    getSession(sessionId).then(setSession).catch(() => undefined);
  }, [sessionId]);

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
        const s = await getSession(sessionId);
        if (s.status === "REPORT_READY") {
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

  const drillLabel = session ? drillTypeLabel(session.drill_type) : "Drill";

  return (
    <PageLayout
      title="Analysing Drill Attempt"
      strip="Operational Mode"
      subtitle={
        session
          ? `${session.cadet_name} · ${drillLabel} · Attempt #${session.attempt_number}`
          : undefined
      }
    >
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <StatusBadge status={progress.status} large />
          <p className="text-sm text-slate-600">
            {wsConnected ? "Live updates connected" : "Polling fallback active"}
          </p>
        </div>

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
                "Analysis failed. Check camera visibility and retake the drill."
              }
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <PrimaryButton onClick={() => navigate("/sessions/new")}>Retake Drill</PrimaryButton>
              <PrimaryButton variant="secondary" onClick={() => navigate("/dashboard")}>
                Back to Dashboard
              </PrimaryButton>
            </div>
          </>
        )}

        {progress.status === "PROCESSING" && (
          <LoadingState message={`Analysing ${drillLabel}...`} />
        )}
      </div>
    </PageLayout>
  );
}
