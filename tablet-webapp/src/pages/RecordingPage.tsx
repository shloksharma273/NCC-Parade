import { useCallback, useEffect, useState } from "react";
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
    if (!sessionId) return;

    let cancelled = false;

    const enablePreview = async () => {
      if (session?.status === "RECORDING") {
        setPreviewActive(true);
        return;
      }

      try {
        await startCameraPreview(sessionId);
        if (!cancelled) {
          setPreviewActive(true);
        }
      } catch (err) {
        if (!cancelled) {
          setError(parseApiError(err));
        }
      }
    };

    if (!loading) {
      enablePreview();
    }

    return () => {
      cancelled = true;
      stopCameraPreview(sessionId).catch(() => undefined);
      setPreviewActive(false);
    };
  }, [sessionId, loading, session?.status]);

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
    setError(null);
    try {
      await stopRecording(sessionId);
      setRecording(false);
      navigate(`/sessions/${sessionId}/processing`);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Recording">
        <LoadingState />
      </PageLayout>
    );
  }

  if (!session) {
    return (
      <PageLayout title="Recording" backTo="/dashboard">
        <ErrorBanner message={error ?? "Session not found."} />
      </PageLayout>
    );
  }

  const canStart = ["CREATED", "READY"].includes(session.status) && !recording;
  const canStop = session.status === "RECORDING" || recording;

  return (
    <PageLayout title="Recording Drill" backTo="/dashboard">
      <div className="space-y-6">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <CameraPreview
          sessionId={session.session_id}
          active={previewActive || recording}
          label={recording ? "Recording Live Feed" : "Camera Preview"}
        />

        <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm text-slate-500">Cadet</p>
              <p className="text-xl font-semibold">{session.cadet_name}</p>
              {session.cadet_id && <p className="text-slate-600">{session.cadet_id}</p>}
            </div>
            <div>
              <p className="text-sm text-slate-500">Drill</p>
              <p className="text-xl font-semibold">{drillTypeLabel(session.drill_type)}</p>
              <p className="text-slate-600">Attempt #{session.attempt_number}</p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <div>
              <p className="text-sm text-slate-500">Session ID</p>
              <p className="font-mono text-sm">{session.session_id}</p>
            </div>
            <StatusBadge status={recording ? "RECORDING" : session.status} large />
          </div>

          <div className="mt-8 text-center">
            <p className="text-sm text-slate-500">Recording Timer</p>
            <p className="text-5xl font-bold tabular-nums">{formatTime(timer)}</p>
          </div>

          <p className="mt-4 text-center text-slate-600">
            {canStart
              ? "Session created. Ready to record."
              : canStop
                ? "Recording in progress. Tap Stop when the drill is complete."
                : `Status: ${session.status}`}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <PrimaryButton onClick={handleStart} disabled={!canStart || actionLoading}>
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
