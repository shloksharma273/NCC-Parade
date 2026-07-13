import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCameraDiagnostics, getCameraSnapshotUrl } from "../api/cameraApi";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { getBackendUrl } from "../utils/backendUrl";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { LoadingState } from "../components/LoadingState";
import { ErrorBanner } from "../components/ErrorBanner";
import type { CameraDiagnostics } from "../api/cameraApi";

export function AdminStatusPage() {
  const navigate = useNavigate();
  const { status, loading, error, refresh } = useBackendStatus();
  const backend = getBackendUrl();
  const [diagnostics, setDiagnostics] = useState<CameraDiagnostics | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [snapshotKey, setSnapshotKey] = useState(0);

  const loadDiagnostics = useCallback(async () => {
    setDiagLoading(true);
    try {
      setDiagnostics(await fetchCameraDiagnostics());
    } catch {
      setDiagnostics(null);
    } finally {
      setDiagLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!backend) navigate("/connect", { replace: true });
    else loadDiagnostics();
  }, [backend, navigate, loadDiagnostics]);

  const snapshotUrl = getCameraSnapshotUrl();

  return (
    <PageLayout title="System Status" strip="Admin Mode" backTo="/dashboard">
      {loading && !status && <LoadingState />}
      {error && <ErrorBanner message={error} />}
      {status && (
        <div className="command-card space-y-4 p-6">
          <div><span className="text-slate-500">Backend URL</span><p className="font-mono break-all">{backend}</p></div>
          <div><span className="text-slate-500">Camera Type</span><p className="font-bold uppercase">{status.camera_type}</p></div>
          {status.camera_type === "ip" && (
            <div><span className="text-slate-500">Camera IP</span><p className="font-mono">{status.camera_host ?? status.camera_id}</p></div>
          )}
          <div><span className="text-slate-500">Connection</span><p className="font-bold">{status.camera_connected ? "Connected" : "Not Connected"}</p></div>
          {status.camera_stream && (
            <div><span className="text-slate-500">Active Stream</span><p className="font-bold uppercase">{status.camera_stream}</p></div>
          )}
          <div><span className="text-slate-500">Model</span><p className="font-bold">{status.model_ready ? "Ready" : "Not Ready"}</p></div>
          <div><span className="text-slate-500">Storage</span><p className="font-bold">{status.storage_available ? "Available" : "Unavailable"}</p></div>
          <div><span className="text-slate-500">Active Session</span><p className="font-mono">{status.active_session_id ?? "None"}</p></div>
        </div>
      )}

      <div className="command-card mt-6 space-y-3 p-6">
        <p className="font-command text-lg font-bold">Camera Diagnostics</p>
        {diagLoading && <LoadingState message="Checking RTSP streams..." />}
        {diagnostics && (
          <>
            <p className="text-sm text-slate-600">{diagnostics.message}</p>
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <p>Main configured: {diagnostics.main_stream_configured ? "Yes" : "No"}</p>
              <p>Main openable: {diagnostics.main_stream_openable ? "Yes" : "No"}</p>
              <p>Sub configured: {diagnostics.sub_stream_configured ? "Yes" : "No"}</p>
              <p>Sub openable: {diagnostics.sub_stream_openable ? "Yes" : "No"}</p>
            </div>
            <p className="text-xs text-slate-500">Last checked: {diagnostics.last_checked_at}</p>
          </>
        )}
      </div>

      {snapshotUrl && (
        <div className="command-card mt-6 p-6">
          <p className="mb-3 font-command text-lg font-bold">Camera Snapshot</p>
          <img
            key={snapshotKey}
            src={`${snapshotUrl}&k=${snapshotKey}`}
            alt="Camera snapshot"
            className="max-h-64 rounded-xl border-2 border-[var(--color-khaki)]"
            onError={() => undefined}
          />
        </div>
      )}

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <PrimaryButton onClick={() => { refresh(); loadDiagnostics(); }}>Refresh Status</PrimaryButton>
        <PrimaryButton variant="secondary" onClick={() => { loadDiagnostics(); setSnapshotKey((k) => k + 1); }}>
          Refresh Snapshot
        </PrimaryButton>
        <PrimaryButton variant="secondary" onClick={() => window.open(`${backend}/pair`, "_blank")}>
          Open Pairing QR (PC)
        </PrimaryButton>
        <PrimaryButton variant="secondary" onClick={() => navigate("/connect")}>
          Change Backend URL
        </PrimaryButton>
      </div>
    </PageLayout>
  );
}
