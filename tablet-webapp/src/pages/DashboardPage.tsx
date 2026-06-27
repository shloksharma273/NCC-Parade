import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { getBackendUrl } from "../utils/backendUrl";

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-white px-4 py-4 ring-1 ring-slate-200">
      <span className="font-medium text-slate-700">{label}</span>
      <span className={`font-semibold ${ok ? "text-green-700" : "text-red-700"}`}>
        {ok ? "OK" : "Not Ready"}
        {detail && <span className="ml-2 text-sm font-normal text-slate-500">{detail}</span>}
      </span>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { status, loading, error, isReady } = useBackendStatus();

  useEffect(() => {
    if (!getBackendUrl()) navigate("/", { replace: true });
  }, [navigate]);

  if (loading && !status) {
    return (
      <PageLayout title="Dashboard">
        <LoadingState message="Checking system status..." />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Dashboard">
      <div className="space-y-6">
        {error && <ErrorBanner message={error} />}

        <div className="grid gap-3">
          <StatusRow label="Backend" ok={!!status && status.backend_status === "ready"} />
          <StatusRow
            label="Camera"
            ok={!!status?.camera_connected}
            detail={status ? `ID ${status.camera_id}` : undefined}
          />
          <StatusRow label="Model" ok={!!status?.model_ready} />
          <StatusRow label="Storage" ok={!!status?.storage_available} />
          <div className="flex items-center justify-between rounded-xl bg-white px-4 py-4 ring-1 ring-slate-200">
            <span className="font-medium text-slate-700">Active Session</span>
            <span className="font-semibold text-slate-800">
              {status?.active_session_id ?? "None"}
            </span>
          </div>
        </div>

        {!status?.camera_connected && (
          <ErrorBanner message="Camera is not connected. Please check the camera connection on the PC." />
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <PrimaryButton onClick={() => navigate("/sessions/new")} disabled={!isReady}>
            New Drill Session
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/sessions/recent")}>
            Recent Sessions
          </PrimaryButton>
          <Link to="/" className="sm:col-span-2">
            <PrimaryButton variant="secondary">Reconnect</PrimaryButton>
          </Link>
        </div>
      </div>
    </PageLayout>
  );
}
