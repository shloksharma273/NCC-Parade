import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, getSession } from "../api/sessionApi";
import { parseApiError } from "../api/client";
import {
  listCameraDevices,
  startDevicePreview,
  stopDevicePreview,
  getDeviceStreamUrl,
  type CameraDevice,
} from "../api/cameraApi";
import { PrimaryButton } from "../components/PrimaryButton";
import { CameraPreview } from "../components/CameraPreview";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageLayout } from "../components/PageLayout";
import { useSessionState } from "../hooks/useSessionState";
import { DRILL_OPTIONS } from "../utils/resultMapper";
import type { SessionStatus } from "../types/session";

// Short blurb under each Front/Side camera-view choice, per drill.
function viewDescription(drillType: string, view: "Front" | "Side"): string {
  if (drillType === "baju_swing") {
    return view === "Front"
      ? "Face-on: fist / thumb closure + arm spread"
      : "Side-on: inter-arm swing angle";
  }
  if (drillType === "tez_chal") {
    return view === "Front"
      ? "Face-on: arms & legs straight + fist closed"
      : "Side-on: arms & legs straight + fist closed";
  }
  if (drillType === "hill_march") {
    return view === "Front"
      ? "Face-on: legs apart ≥50° + arms/legs straight + head"
      : "Side-on: legs apart ≥70° + arms/legs straight + head";
  }
  return view === "Front" ? "Face-on camera angle" : "Side-on camera angle";
}

export function NewSessionPage() {
  const navigate = useNavigate();
  const { setCurrentSession, retakeContext, setRetakeContext } = useSessionState();

  const [cadetId, setCadetId] = useState(retakeContext?.cadet_id ?? "");
  const [cadetName, setCadetName] = useState(retakeContext?.cadet_name ?? "");
  const [squad, setSquad] = useState("");
  const [unit, setUnit] = useState("");
  const [drillType, setDrillType] = useState(retakeContext?.drill_type ?? "kadam_tal");
  const [cameraId, setCameraId] = useState(retakeContext?.camera_id ?? "0");
  const [cameraView, setCameraView] = useState<string>(
    DRILL_OPTIONS.find((d) => d.value === (retakeContext?.drill_type ?? "kadam_tal"))?.cameraView ?? "Side",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Camera picker (live thumbnails instead of typing an index) ---
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [previewActive, setPreviewActive] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  // Keep the preview (and thus the warm camera) alive when navigating forward to readiness.
  const keepPreviewOnExit = useRef(false);

  const selectedDrill = DRILL_OPTIONS.find((d) => d.value === drillType);

  useEffect(() => {
    if (retakeContext) setRetakeContext(null);
  }, [retakeContext, setRetakeContext]);

  // Start a live preview of the given camera (session-less device preview).
  const previewCamera = async (id: string) => {
    try {
      await startDevicePreview(id);
      setPreviewActive(true);
      setStreamKey((k) => k + 1);
    } catch {
      setPreviewActive(false);
    }
  };

  // Load the available cameras once, pick a sensible default, and preview it.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { devices: found } = await listCameraDevices();
        if (cancelled) return;
        setDevices(found);
        const available = found.filter((d) => d.available);
        const stillValid = available.some((d) => String(d.index) === cameraId);
        const initial = stillValid ? cameraId : available.length ? String(available[0].index) : cameraId;
        if (initial !== cameraId) setCameraId(initial);
        if (available.length) void previewCamera(initial);
      } catch {
        if (!cancelled) setDevices([]);
      } finally {
        if (!cancelled) setDevicesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      // Release the camera on leave UNLESS we're proceeding to readiness (keep it warm).
      if (!keepPreviewOnExit.current) void stopDevicePreview();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectCamera = (id: string) => {
    setCameraId(id);
    void previewCamera(id);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cadetName.trim()) {
      setError("Cadet name is required.");
      return;
    }
    if (selectedDrill && !selectedDrill.backendSupported) {
      setError(`${selectedDrill.label} is not available yet.`);
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
        camera_view: cameraView,
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
      keepPreviewOnExit.current = true; // keep the camera warm through to readiness
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
                  onClick={() => {
                    if (drill.backendSupported) {
                      setDrillType(drill.value);
                      setCameraView(drill.cameraView);
                    }
                  }}
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

        {selectedDrill?.viewSelectable && (
          <div>
            <p className="mb-3 font-command text-xl font-bold">Camera View</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {(["Front", "Side"] as const).map((view) => {
                const active = cameraView === view;
                return (
                  <button
                    key={view}
                    type="button"
                    onClick={() => setCameraView(view)}
                    className={`relative p-4 text-left transition-all ${
                      active
                        ? "rounded-xl border-4 border-[var(--color-army-green)] bg-[var(--color-sand)] shadow-md ring-2 ring-[var(--color-army-green)] ring-offset-2"
                        : "command-card hover:border-[var(--color-army-green)] hover:bg-[var(--color-sand)]"
                    }`}
                  >
                    {active && (
                      <span className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-army-green)] text-sm font-bold text-white">
                        ✓
                      </span>
                    )}
                    <p className="font-command text-lg font-bold">{view} View</p>
                    <p className="text-sm text-slate-600">{viewDescription(drillType, view)}</p>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="font-command text-xl font-bold">Select Camera</p>
            <button
              type="button"
              onClick={async () => {
                setDevicesLoading(true);
                try {
                  const { devices: found } = await listCameraDevices(true);
                  setDevices(found);
                } finally {
                  setDevicesLoading(false);
                }
              }}
              className="text-sm font-semibold text-[var(--color-army-green)] underline"
            >
              Refresh
            </button>
          </div>

          {devicesLoading && devices.length === 0 ? (
            <p className="text-sm text-slate-500">Detecting cameras…</p>
          ) : devices.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-3">
              {devices.map((device) => {
                const id = String(device.index);
                const selected = cameraId === id;
                return (
                  <button
                    key={id}
                    type="button"
                    disabled={!device.available}
                    onClick={() => device.available && selectCamera(id)}
                    className={`relative overflow-hidden rounded-xl border-2 text-left transition-all ${
                      !device.available
                        ? "cursor-not-allowed border-slate-200 opacity-50"
                        : selected
                          ? "border-4 border-[var(--color-army-green)] ring-2 ring-[var(--color-army-green)] ring-offset-2"
                          : "border-[var(--color-khaki)] hover:border-[var(--color-army-green)]"
                    }`}
                  >
                    <div className="aspect-video bg-black">
                      {device.thumbnail ? (
                        <img src={device.thumbnail} alt={device.label} className="h-full w-full object-contain" />
                      ) : (
                        <div className="flex h-full items-center justify-center text-xs text-slate-400">No preview</div>
                      )}
                    </div>
                    <div className="flex items-center justify-between px-3 py-2">
                      <span className="font-semibold">{device.label}</span>
                      {selected && (
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-army-green)] text-xs font-bold text-white">✓</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-[var(--color-fail)]">
                No cameras detected. Enter a camera index manually, or press Refresh.
              </p>
              <input
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                placeholder="0"
                className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg"
              />
            </div>
          )}

          {devices.some((d) => d.available) && (
            <div className="mt-3">
              <CameraPreview
                streamUrlOverride={getDeviceStreamUrl()}
                active={previewActive}
                streamKey={streamKey}
                label="Selected Camera — Live"
              />
            </div>
          )}
        </div>

        <PrimaryButton type="submit" disabled={loading}>
          {loading ? "Creating..." : "Continue to Readiness Check"}
        </PrimaryButton>
      </form>
    </PageLayout>
  );
}
