import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { listSessions } from "../api/sessionApi";
import { useState, useCallback } from "react";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { getBackendUrl } from "../utils/backendUrl";
import { drillTypeLabel, resultLabel } from "../utils/resultMapper";
import { formatDateTime } from "../utils/formatTime";
import type { SessionListItem } from "../types/session";

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail?: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-[var(--color-khaki)] bg-white px-4 py-4">
      <span className="font-medium">{label}</span>
      <span className={`font-bold ${ok ? "text-[var(--color-success)]" : "text-[var(--color-fail)]"}`}>
        {ok ? "OK" : "Not Ready"}
        {detail && <span className="ml-2 text-sm font-normal text-slate-500">{detail}</span>}
      </span>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { status, loading, error, isReady } = useBackendStatus();
  const [recent, setRecent] = useState<SessionListItem[]>([]);

  const loadRecent = useCallback(async () => {
    try {
      const data = await listSessions(5);
      setRecent(data.sessions);
    } catch {
      setRecent([]);
    }
  }, []);

  useEffect(() => {
    if (!getBackendUrl()) navigate("/connect", { replace: true });
    else loadRecent();
  }, [navigate, loadRecent]);

  if (loading && !status) {
    return (
      <PageLayout title="Dashboard" strip="Command Console">
        <LoadingState message="Checking system status..." />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="Drill Recognition Console" strip="Operational Mode" subtitle="Instructor Command Center">
      <div className="space-y-6">
        {error && <ErrorBanner message={error} />}

        <div className="grid gap-3">
          <StatusRow label="Backend" ok={!!status && status.backend_status === "ready"} />
          <StatusRow label="Camera" ok={!!status?.camera_connected} detail={status ? `ID ${status.camera_id}` : undefined} />
          <StatusRow label="Model" ok={!!status?.model_ready} />
          <StatusRow label="Storage" ok={!!status?.storage_available} />
        </div>

        {!status?.camera_connected && (
          <ErrorBanner message="Camera is not connected. Check the camera on the PC before recording." />
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <PrimaryButton onClick={() => navigate("/sessions/new")} disabled={!isReady}>
            Start New Drill
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/sessions/recent")}>
            Recent Reports
          </PrimaryButton>
          <PrimaryButton variant="secondary" onClick={() => navigate("/admin")}>
            System Check
          </PrimaryButton>
          <Link to="/connect" className="sm:col-span-2">
            <PrimaryButton variant="secondary">Reconnect</PrimaryButton>
          </Link>
        </div>

        {recent.length > 0 && (
          <div className="command-card overflow-hidden">
            <div className="rank-strip">Recent Attempts</div>
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--color-deep-olive)] text-white">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Cadet</th>
                  <th className="px-4 py-3">Drill</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((s) => (
                  <tr
                    key={s.session_id}
                    className="cursor-pointer border-t hover:bg-[var(--color-sand)]"
                    onClick={() => navigate(s.status === "REPORT_READY" ? `/sessions/${s.session_id}/report` : `/sessions/${s.session_id}/recording`)}
                  >
                    <td className="px-4 py-3">{formatDateTime(s.created_at)}</td>
                    <td className="px-4 py-3 font-medium">{s.cadet_name}</td>
                    <td className="px-4 py-3">{drillTypeLabel(s.drill_type)}</td>
                    <td className="px-4 py-3">{s.score ?? "—"}</td>
                    <td className="px-4 py-3">{s.result ? resultLabel(s.result) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
