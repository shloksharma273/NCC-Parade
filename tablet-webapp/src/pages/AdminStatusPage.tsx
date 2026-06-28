import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { getBackendUrl } from "../utils/backendUrl";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { LoadingState } from "../components/LoadingState";
import { ErrorBanner } from "../components/ErrorBanner";

export function AdminStatusPage() {
  const navigate = useNavigate();
  const { status, loading, error, refresh } = useBackendStatus();
  const backend = getBackendUrl();

  useEffect(() => {
    if (!backend) navigate("/connect", { replace: true });
  }, [backend, navigate]);

  return (
    <PageLayout title="System Status" strip="Admin Mode" backTo="/dashboard">
      {loading && !status && <LoadingState />}
      {error && <ErrorBanner message={error} />}
      {status && (
        <div className="command-card space-y-4 p-6">
          <div><span className="text-slate-500">Backend URL</span><p className="font-mono break-all">{backend}</p></div>
          <div><span className="text-slate-500">Camera</span><p className="font-bold">{status.camera_connected ? "Connected" : "Not Connected"}</p></div>
          <div><span className="text-slate-500">Model</span><p className="font-bold">{status.model_ready ? "Ready" : "Not Ready"}</p></div>
          <div><span className="text-slate-500">Storage</span><p className="font-bold">{status.storage_available ? "Available" : "Unavailable"}</p></div>
          <div><span className="text-slate-500">Active Session</span><p className="font-mono">{status.active_session_id ?? "None"}</p></div>
        </div>
      )}
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <PrimaryButton onClick={refresh}>Refresh Status</PrimaryButton>
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
