import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCameraDevices } from "../api/cameraApi";
import type { CameraDevice } from "../api/cameraApi";
import { parseApiError } from "../api/client";
import { CameraTile } from "./CameraTile";
import { LoadingState } from "./LoadingState";

type CameraSelectorProps = {
  value: string;
  onChange: (deviceId: string) => void;
};

/**
 * Camera chooser grid: every USB and IP camera the backend can see, each with a
 * live thumbnail, so the operator picks by looking rather than by guessing an
 * index.
 */
export function CameraSelector({ value, onChange }: CameraSelectorProps) {
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [rescanning, setRescanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh: boolean) => {
      if (refresh) setRescanning(true);
      // Only the first load shows a spinner; later polls update in place.
      try {
        const data = await fetchCameraDevices(refresh);
        setDevices(data.devices);
        setError(null);

        // Auto-pick when the current choice cannot be used, so the form is
        // never submitted pointing at a camera that isn't there.
        const chosen = data.devices.find((d) => d.device_id === value);
        if (!chosen?.available && data.default_device_id) {
          onChange(data.default_device_id);
        }
      } catch (err) {
        setError(parseApiError(err));
      } finally {
        setLoading(false);
        setRescanning(false);
      }
    },
    // `value` is read as a snapshot inside; re-running on every keystroke of the
    // selection would restart discovery needlessly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onChange],
  );

  useEffect(() => {
    load(false);
    // Re-read the cached device list periodically so a camera that fails to
    // stream reports why, instead of leaving its tile spinning. This hits the
    // discovery cache, so it does not re-probe the hardware.
    const id = window.setInterval(() => load(false), 4000);
    return () => window.clearInterval(id);
  }, [load]);

  const available = devices.filter((d) => d.available);
  const unavailable = devices.filter((d) => !d.available);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="font-command text-xl font-bold">Select Camera</p>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={rescanning}
          className="rounded-lg border-2 border-[var(--color-khaki)] px-3 py-1.5 text-sm font-semibold hover:bg-[var(--color-sand)] disabled:opacity-50"
        >
          {rescanning ? "Scanning..." : "Rescan"}
        </button>
      </div>

      {loading && <LoadingState message="Looking for cameras..." />}

      {!loading && error && (
        <div className="command-card border-[var(--color-fail)] p-4 text-sm">
          <p className="font-semibold text-[var(--color-fail)]">Could not list cameras</p>
          <p className="mt-1 text-slate-600">{error}</p>
        </div>
      )}

      {!loading && !error && devices.length === 0 && (
        <div className="command-card p-4 text-sm text-slate-600">
          No cameras were detected. Connect a USB camera or configure an IP camera
          in <span className="font-mono">.env</span>, then press Rescan.
        </div>
      )}

      {!loading && available.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {available.map((device) => (
            <CameraTile
              key={device.device_id}
              device={device}
              selected={value === device.device_id}
              onSelect={onChange}
            />
          ))}
        </div>
      )}

      {!loading && unavailable.some((d) => d.status === "unauthorized") && (
        <div className="command-card mt-4 border-[var(--color-fail)] p-4">
          <p className="text-sm font-semibold">A network camera needs credentials</p>
          <p className="mt-1 text-sm text-slate-600">
            It is online but rejects the saved username and password.
          </p>
          <Link
            to="/admin/camera"
            className="mt-3 inline-block rounded-lg border-2 border-[var(--color-army-green)] px-4 py-2 text-sm font-semibold hover:bg-[var(--color-sand)]"
          >
            Configure Camera
          </Link>
        </div>
      )}

      {!loading && unavailable.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Unavailable ({unavailable.length})
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {unavailable.map((device) => (
              <CameraTile
                key={device.device_id}
                device={device}
                selected={false}
                onSelect={onChange}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
