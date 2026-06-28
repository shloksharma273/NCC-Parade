import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { startCameraPreview, stopCameraPreview } from "../api/cameraApi";
import { getSession, startRecording, stopRecording } from "../api/sessionApi";
import { parseApiError } from "../api/client";
import { CameraPreview } from "../components/CameraPreview";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { StatusBadge } from "../components/StatusBadge";
import { useSessionState } from "../hooks/useSessionState";
import { formatTime } from "../utils/formatTime";
import { drillTypeLabel } from "../utils/resultMapper";
import type { Session } from "../types/session";

export function RecordingPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { setCurrentSession } = useSessionState();

  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timer, setTimer] = useState(0);
  const [recording, setRecording] = useState(false);
  const [previewActive, setPreviewActive] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const previewStarted = useRef(false);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await getSession(sessionId);
      setSession(data);
      setCurrentSession({
        session_id: data.session_id,
        cadet_id: data.cadet_id ?? undefined,
        cadet_name: data.cadet_name,
        drill_type: data.drill_type,
        attempt_number: data.attempt_number,
        camera_id: data.camera_id,
        status: data.status,
      });
      if (data.status === "PROCESSING" || data.status === "SAVING") {
        navigate(`/sessions/${sessionId}/processing`, { replace: true });
      } else if (data.status === "REPORT_READY") {
        navigate(`/sessions/${sessionId}/report`, { replace: true });
      } else if (data.status === "RECORDING") {
        setRecording(true);
        setPreviewActive(true);
      }
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, navigate, setCurrentSession]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!sessionId || loading) return;

    let cancelled = false;

    const ensurePreview = async () => {
      try {
        await startCameraPreview(sessionId);
        if (!cancelled) {
          previewStarted.current = true;
          setPreviewActive(true);
          setStreamKey((k) => k + 1);
        }
      } catch (err) {
        if (!cancelled) setError(parseApiError(err));
      }
    };

    ensurePreview();

    return () => {
      cancelled = true;
      if (previewStarted.current && sessionId) {
        stopCameraPreview(sessionId).catch(() => undefined);
        previewStarted.current = false;
      }
    };
  }, [sessionId, loading]);

  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => setTimer((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [recording]);

  const handleStart = async () => {
    if (!sessionId) return;
    setActionLoading(true);
    setError(null);
    try {
      await startRecording(sessionId);
      setRecording(true);
      setPreviewActive(true);
      setStreamKey((k) => k + 1);
      setTimer(0);
      await load();
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    if (!sessionId) return;
    setActionLoading(true);
    setSaving(true);
    setError(null);
    try {
      await stopRecording(sessionId);
      setRecording(false);
      navigate(`/sessions/${sessionId}/processing`);
    } catch (err) {
      setSaving(false);
      setError(parseApiError(err));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Recording" strip="Operational Mode">
        <LoadingState />
      </PageLayout>
    );
  }

  if (!session) {
    return (
      <PageLayout title="Recording" strip="Operational Mode" backTo="/dashboard">
        <ErrorBanner message={error ?? "Session not found."} />
      </PageLayout>
    );
  }

  const canStart = ["CREATED", "READY"].includes(session.status) && !recording && !saving;
  const canStop = session.status === "RECORDING" || recording;

  const statusBanner = saving
    ? "SAVING VIDEO"
    : recording
      ? `RECORDING — ${formatTime(timer)}`
      : "READY TO RECORD";

  return (
    <PageLayout
      title="Recording Drill"
      strip="Operational Mode"
      subtitle={`${session.cadet_name} · ${drillTypeLabel(session.drill_type)} · Attempt #${session.attempt_number}`}
      backTo={`/sessions/${sessionId}/readiness`}
    >
      <div className="space-y-6">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className={`command-card py-4 text-center ${recording ? "bg-[var(--color-command-red)] text-white" : "bg-[var(--color-deep-olive)] text-[var(--color-sand)]"}`}>
          <p className="font-command text-2xl font-bold tracking-wide md:text-3xl">{statusBanner}</p>
          <div className="mt-2 flex justify-center">
            <StatusBadge status={recording ? "RECORDING" : session.status} large />
          </div>
        </div>

        <CameraPreview
          sessionId={session.session_id}
          active={previewActive || recording}
          streamKey={streamKey}
          label={recording ? "Recording Live Feed" : "Camera Preview"}
          showAlignmentGuide={!recording}
        />

        <div className="grid gap-4">
          <PrimaryButton onClick={handleStart} disabled={!canStart || actionLoading} variant="command">
            Start Recording
          </PrimaryButton>
          <PrimaryButton
            variant="danger"
            onClick={handleStop}
            disabled={!canStop || actionLoading}
          >
            Stop Recording
          </PrimaryButton>
        </div>

        <PrimaryButton variant="secondary" onClick={() => navigate("/dashboard")}>
          Cancel Session
        </PrimaryButton>
      </div>
    </PageLayout>
  );
}
