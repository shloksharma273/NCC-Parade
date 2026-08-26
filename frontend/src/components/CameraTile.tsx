import { useEffect, useRef, useState } from "react";
import { getDeviceSnapshotUrl } from "../api/cameraApi";
import type { CameraDevice } from "../api/cameraApi";

type CameraTileProps = {
  device: CameraDevice;
  selected: boolean;
  onSelect: (deviceId: string) => void;
  /** Milliseconds between snapshot refreshes. */
  pollMs?: number;
};

const KIND_LABEL: Record<string, string> = { usb: "USB", ip: "IP" };

const STATUS_TEXT: Record<string, string> = {
  ready: "Ready",
  unreachable: "Not reachable",
  unauthorized: "Needs credentials",
  unconfigured: "Not configured",
  detected: "Detected — not configured",
};

/** Backend preview-failure codes, in words an operator can act on. */
const PREVIEW_ERROR_TEXT: Record<string, string> = {
  IP_CAMERA_NOT_REACHABLE:
    "Stream would not open. Check the RTSP URL, username and password.",
  CAMERA_NOT_FOUND: "Camera could not be opened.",
  RTSP_URL_MISSING: "No RTSP URL configured for this camera.",
  DEVICE_NOT_FOUND: "Camera is no longer present.",
  PREVIEW_STREAM_FAILED: "Stream stopped sending frames.",
  PREVIEW_OPEN_FAILED: "Stream would not open.",
};

/**
 * One camera in the chooser grid, with a thumbnail refreshed by polling stills.
 *
 * Deliberately not an MJPEG stream: browsers allow only a handful of concurrent
 * connections per host, and an MJPEG connection never closes, so a grid of them
 * would consume every slot and stall the page's other requests. A once-a-second
 * still is enough to answer "where is this camera pointing".
 */
export function CameraTile({ device, selected, onSelect, pollMs = 1000 }: CameraTileProps) {
  const [tick, setTick] = useState(0);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const [frameFailed, setFrameFailed] = useState(false);
  const inFlight = useRef(false);

  const usable = device.available;

  const previewFailed = device.preview_state === "failed";
  const previewErrorText = device.preview_error
    ? PREVIEW_ERROR_TEXT[device.preview_error] ?? device.preview_error
    : null;

  useEffect(() => {
    if (!usable || previewFailed) return;
    // Advance only when the previous image settled, so a slow or warming-up
    // camera cannot pile up requests.
    const id = window.setInterval(() => {
      if (!inFlight.current) {
        inFlight.current = true;
        setTick((t) => t + 1);
      }
    }, pollMs);
    return () => window.clearInterval(id);
  }, [usable, previewFailed, pollMs]);

  // A stream the backend has given up on must not keep polling — it would sit
  // on "Connecting..." indefinitely with no explanation.
  const snapshotUrl =
    usable && !previewFailed ? getDeviceSnapshotUrl(device.device_id, tick) : null;
  const resolution = device.capabilities?.width
    ? `${device.capabilities.width}×${device.capabilities.height}`
    : null;

  return (
    <button
      type="button"
      disabled={!usable}
      onClick={() => usable && onSelect(device.device_id)}
      aria-pressed={selected}
      className={`relative overflow-hidden text-left transition-all ${
        !usable
          ? "cursor-not-allowed rounded-xl border-2 border-slate-200 bg-slate-100 opacity-70"
          : selected
            ? "rounded-xl border-4 border-[var(--color-army-green)] bg-[var(--color-sand)] shadow-md ring-2 ring-[var(--color-army-green)] ring-offset-2"
            : "command-card hover:border-[var(--color-army-green)] hover:bg-[var(--color-sand)]"
      }`}
    >
      {selected && usable && (
        <span className="absolute right-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-army-green)] text-sm font-bold text-white shadow">
          ✓
        </span>
      )}

      <div className="relative aspect-video w-full bg-black">
        {snapshotUrl && (
          <img
            key={snapshotUrl}
            src={snapshotUrl}
            alt={`${device.label} preview`}
            className={`h-full w-full object-contain transition-opacity ${
              frameLoaded ? "opacity-100" : "opacity-0"
            }`}
            onLoad={() => {
              inFlight.current = false;
              setFrameLoaded(true);
              setFrameFailed(false);
            }}
            onError={() => {
              inFlight.current = false;
              setFrameFailed(true);
            }}
          />
        )}

        {!frameLoaded && (
          <div className="absolute inset-0 flex items-center justify-center px-3 text-center text-xs text-slate-400">
            {previewFailed
              ? previewErrorText ?? "Stream failed"
              : !usable
                ? STATUS_TEXT[device.status] ?? "Unavailable"
                : frameFailed
                  ? "Starting camera..."
                  : "Connecting..."}
          </div>
        )}

        <span
          className={`absolute left-2 top-2 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
            device.kind === "ip" ? "bg-sky-600 text-white" : "bg-[var(--color-deep-olive)] text-white"
          }`}
        >
          {KIND_LABEL[device.kind] ?? device.kind}
        </span>
      </div>

      <div className="space-y-1 p-3">
        <p className="font-command text-base font-bold leading-tight">{device.label}</p>
        <p className="font-mono text-[11px] text-slate-500">{device.device_id}</p>
        <p
          className={`text-xs font-semibold ${
            usable ? "text-[var(--color-success)]" : "text-[var(--color-fail)]"
          }`}
        >
          {usable ? "✓ " : "✕ "}
          {STATUS_TEXT[device.status] ?? device.status}
          {usable && resolution ? ` · ${resolution}` : ""}
        </p>
        {!usable && <p className="text-xs leading-snug text-slate-500">{device.message}</p>}
        {usable && previewFailed && previewErrorText && (
          <p className="text-xs leading-snug text-[var(--color-fail)]">{previewErrorText}</p>
        )}
      </div>
    </button>
  );
}
