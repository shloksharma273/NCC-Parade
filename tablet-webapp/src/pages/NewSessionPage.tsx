import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, getSession } from "../api/sessionApi";
import { parseApiError } from "../api/client";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageLayout } from "../components/PageLayout";
import { useSessionState } from "../hooks/useSessionState";
import { SUPPORTED_DRILL_TYPES } from "../utils/resultMapper";
import type { SessionStatus } from "../types/session";

export function NewSessionPage() {
  const navigate = useNavigate();
  const { setCurrentSession, retakeContext, setRetakeContext } = useSessionState();

  const [cadetId, setCadetId] = useState(retakeContext?.cadet_id ?? "");
  const [cadetName, setCadetName] = useState(retakeContext?.cadet_name ?? "");
  const [drillType, setDrillType] = useState(retakeContext?.drill_type ?? "kadam_tal");
  const [cameraId, setCameraId] = useState(retakeContext?.camera_id ?? "0");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (retakeContext) setRetakeContext(null);
  }, [retakeContext, setRetakeContext]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cadetName.trim()) {
      setError("Cadet name is required.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const created = await createSession({
        cadet_id: cadetId.trim() || undefined,
        cadet_name: cadetName.trim(),
        drill_type: drillType,
        camera_id: cameraId,
      });
      const session = await getSession(created.session_id);
      setCurrentSession({
        session_id: session.session_id,
        cadet_id: session.cadet_id ?? undefined,
        cadet_name: session.cadet_name,
        drill_type: session.drill_type,
        attempt_number: session.attempt_number,
        camera_id: session.camera_id,
        status: session.status as SessionStatus,
      });
      navigate(`/sessions/${created.session_id}/recording`);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="New Drill Session" backTo="/dashboard">
      <form onSubmit={submit} className="mx-auto max-w-xl space-y-5">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <label className="block">
          <span className="mb-2 block font-semibold">Cadet ID</span>
          <input
            value={cadetId}
            onChange={(e) => setCadetId(e.target.value)}
            placeholder="C101"
            className="w-full rounded-xl border border-slate-300 px-4 py-4 text-lg"
          />
        </label>

        <label className="block">
          <span className="mb-2 block font-semibold">Cadet Name *</span>
          <input
            value={cadetName}
            onChange={(e) => setCadetName(e.target.value)}
            required
            placeholder="Raj Kumar"
            className="w-full rounded-xl border border-slate-300 px-4 py-4 text-lg"
          />
        </label>

        <label className="block">
          <span className="mb-2 block font-semibold">Drill Type</span>
          <select
            value={drillType}
            onChange={(e) => setDrillType(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-4 py-4 text-lg"
          >
            {SUPPORTED_DRILL_TYPES.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
                {!d.backendSupported ? " (coming soon)" : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block font-semibold">Camera ID</span>
          <input
            value={cameraId}
            onChange={(e) => setCameraId(e.target.value)}
            className="w-full rounded-xl border border-slate-300 px-4 py-4 text-lg"
          />
        </label>

        <PrimaryButton type="submit" disabled={loading}>
          {loading ? "Creating..." : "Create Session"}
        </PrimaryButton>
      </form>
    </PageLayout>
  );
}
