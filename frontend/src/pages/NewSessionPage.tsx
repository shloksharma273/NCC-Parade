import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, getSession } from "../api/sessionApi";
import { parseApiError } from "../api/client";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageLayout } from "../components/PageLayout";
import { useSessionState } from "../hooks/useSessionState";
import { DRILL_OPTIONS } from "../utils/resultMapper";
import type { SessionStatus } from "../types/session";

export function NewSessionPage() {
  const navigate = useNavigate();
  const { setCurrentSession, retakeContext, setRetakeContext } = useSessionState();

  const [cadetId, setCadetId] = useState(retakeContext?.cadet_id ?? "");
  const [cadetName, setCadetName] = useState(retakeContext?.cadet_name ?? "");
  const [squad, setSquad] = useState("");
  const [unit, setUnit] = useState("");
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
    const selected = DRILL_OPTIONS.find((d) => d.value === drillType);
    if (selected && !selected.backendSupported) {
      setError(`${selected.label} is not available yet.`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const created = await createSession({
        cadet_id: cadetId.trim() || undefined,
        cadet_name: cadetName.trim(),
        squad: squad.trim() || undefined,
        unit: unit.trim() || undefined,
        drill_type: drillType,
        camera_id: cameraId,
        camera_view: selected?.cameraView,
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
      navigate(`/sessions/${created.session_id}/readiness`);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="New Drill Session" strip="Operational Mode" backTo="/dashboard">
      <form onSubmit={submit} className="mx-auto max-w-2xl space-y-5">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <div className="command-card grid gap-4 p-5 md:grid-cols-2">
          <label className="block">
            <span className="mb-2 block font-semibold">Cadet ID</span>
            <input value={cadetId} onChange={(e) => setCadetId(e.target.value)} placeholder="C101" className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg" />
          </label>
          <label className="block">
            <span className="mb-2 block font-semibold">Cadet Name *</span>
            <input value={cadetName} onChange={(e) => setCadetName(e.target.value)} required placeholder="Raj Kumar" className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg" />
          </label>
          <label className="block">
            <span className="mb-2 block font-semibold">Squad / Unit</span>
            <input value={squad} onChange={(e) => setSquad(e.target.value)} placeholder="Alpha Squad" className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg" />
          </label>
          <label className="block">
            <span className="mb-2 block font-semibold">Platoon / Company</span>
            <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Platoon B" className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg" />
          </label>
        </div>

        <div>
          <p className="mb-3 font-command text-xl font-bold">Select Drill</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {DRILL_OPTIONS.map((drill) => {
              const selected = drillType === drill.value;
              return (
                <button
                  key={drill.value}
                  type="button"
                  disabled={!drill.backendSupported}
                  onClick={() => drill.backendSupported && setDrillType(drill.value)}
                  className={`relative p-4 text-left transition-all ${
                    !drill.backendSupported
                      ? "cursor-not-allowed rounded-xl border-2 border-slate-200 bg-slate-100 opacity-60"
                      : selected
                        ? "rounded-xl border-4 border-[var(--color-army-green)] bg-[var(--color-sand)] shadow-md ring-2 ring-[var(--color-army-green)] ring-offset-2"
                        : "command-card hover:border-[var(--color-army-green)] hover:bg-[var(--color-sand)]"
                  }`}
                >
                  {selected && drill.backendSupported && (
                    <span className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-army-green)] text-sm font-bold text-white">
                      ✓
                    </span>
                  )}
                  <p className={`font-command text-lg font-bold ${selected && drill.backendSupported ? "text-[var(--color-deep-olive)]" : ""}`}>
                    {drill.label}
                  </p>
                  <p className="text-sm text-slate-600">Camera: {drill.cameraView}</p>
                  <p className="mt-1 text-xs font-semibold uppercase">
                    {drill.backendSupported ? "Available" : "Coming Soon"}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <label className="block">
          <span className="mb-2 block font-semibold">Camera ID</span>
          <input value={cameraId} onChange={(e) => setCameraId(e.target.value)} className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg" />
        </label>

        <PrimaryButton type="submit" disabled={loading}>
          {loading ? "Creating..." : "Continue to Readiness Check"}
        </PrimaryButton>
      </form>
    </PageLayout>
  );
}
