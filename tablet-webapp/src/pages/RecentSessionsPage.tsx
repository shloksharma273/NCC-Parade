import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions } from "../api/sessionApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/formatTime";
import { drillTypeLabel, resultLabel } from "../utils/resultMapper";
import type { SessionListItem } from "../types/session";

export function RecentSessionsPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSessions(20);
      setSessions(data.sessions);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openSession = (session: SessionListItem) => {
    if (session.status === "REPORT_READY") {
      navigate(`/sessions/${session.session_id}/report`);
    } else if (session.status === "PROCESSING" || session.status === "SAVING") {
      navigate(`/sessions/${session.session_id}/processing`);
    } else if (session.status === "RECORDING") {
      navigate(`/sessions/${session.session_id}/recording`);
    } else if (session.status === "FAILED") {
      navigate(`/sessions/${session.session_id}/processing`);
    } else {
      navigate(`/sessions/${session.session_id}/recording`);
    }
  };

  return (
    <PageLayout title="Recent Sessions" backTo="/dashboard">
      {loading && <LoadingState />}
      {error && <ErrorBanner message={error} />}

      {!loading && sessions.length === 0 && (
        <p className="text-lg text-slate-600">No sessions found.</p>
      )}

      {!loading && sessions.length > 0 && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-800 text-white">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Cadet</th>
                <th className="px-4 py-3">Drill</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Result</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr
                  key={session.session_id}
                  onClick={() => openSession(session)}
                  className="cursor-pointer border-t border-slate-100 hover:bg-blue-50 even:bg-slate-50"
                >
                  <td className="px-4 py-4">{formatDateTime(session.created_at)}</td>
                  <td className="px-4 py-4 font-medium">{session.cadet_name}</td>
                  <td className="px-4 py-4">{drillTypeLabel(session.drill_type)}</td>
                  <td className="px-4 py-4">
                    <StatusBadge status={session.status} />
                  </td>
                  <td className="px-4 py-4">{session.score ?? "—"}</td>
                  <td className="px-4 py-4">
                    {session.result ? resultLabel(session.result) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
