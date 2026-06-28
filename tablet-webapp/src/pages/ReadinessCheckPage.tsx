import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSessionReadiness } from "../api/readinessApi";
import { startCameraPreview, stopCameraPreview } from "../api/cameraApi";
import { parseApiError } from "../api/client";
import { CameraPreview } from "../components/CameraPreview";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { drillTypeLabel } from "../utils/resultMapper";
import { getSession } from "../api/sessionApi";
import type { Session } from "../types/session";

export function ReadinessCheckPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const [cameraConnected, setCameraConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewActive, setPreviewActive] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const keepPreviewOnExit = useRef(false);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [sess, readiness] = await Promise.all([getSession(sessionId), getSessionReadiness(sessionId)]);
      setSession(sess);
      const cameraCheck = readiness.checks.find((c) => c.key === "camera_connected");
      setCameraConnected(cameraCheck?.status === "pass");
      setError(null);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!sessionId || loading) return;

    let cancelled = false;
    startCameraPreview(sessionId)
      .then(() => {
        if (!cancelled) {
          setPreviewActive(true);
          setStreamKey((k) => k + 1);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(parseApiError(err));
      });

    // Keep preview running when navigating to recording — avoids stream freeze.
    return () => {
      cancelled = true;
      if (!keepPreviewOnExit.current && sessionId) {
        stopCameraPreview(sessionId).catch(() => undefined);
      }
    };
  }, [sessionId, loading]);

  if (loading) {
    return (
      <PageLayout title="Readiness Check" strip="Pre-Drill">
        <LoadingState />
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Readiness Check"
      strip="Pre-Drill Verification"
      subtitle={session ? `${session.cadet_name} · ${drillTypeLabel(session.drill_type)} · Attempt #${session.attempt_number}` : undefined}
      backTo="/dashboard"
    >
      <div className="space-y-6">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        {sessionId && (
          <CameraPreview sessionId={sessionId} active={previewActive} streamKey={streamKey} label="Live Preview" />
        )}

        <div
          className={`command-card flex items-center justify-between px-5 py-4 ${
            cameraConnected ? "border-[var(--color-success)]" : "border-[var(--color-fail)]"
          }`}
        >
          <span className="font-semibold">Camera Connected</span>
          <span className={`text-lg font-bold ${cameraConnected ? "text-[var(--color-success)]" : "text-[var(--color-fail)]"}`}>
            {cameraConnected ? "✓ Yes" : "✕ No"}
          </span>
        </div>

        <PrimaryButton
          disabled={!cameraConnected}
          onClick={() => {
            keepPreviewOnExit.current = true;
            navigate(`/sessions/${sessionId}/recording`);
          }}
        >
          Continue to Recording
        </PrimaryButton>
      </div>
    </PageLayout>
  );
}
