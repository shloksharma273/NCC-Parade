import { getCameraStreamUrl } from "../api/cameraApi";

type CameraPreviewProps = {
  sessionId: string;
  active: boolean;
  label?: string;
};

export function CameraPreview({ sessionId, active, label = "Live Camera" }: CameraPreviewProps) {
  const streamUrl = active ? getCameraStreamUrl(sessionId) : null;

  return (
    <div className="overflow-hidden rounded-2xl bg-black shadow-sm ring-1 ring-slate-200">
      <div className="flex items-center justify-between bg-slate-900 px-4 py-2">
        <p className="text-sm font-medium text-white">{label}</p>
        {active && (
          <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-400" />
            Live
          </span>
        )}
      </div>

      <div className="aspect-video bg-slate-950">
        {streamUrl ? (
          <img
            src={streamUrl}
            alt="Live camera preview"
            className="h-full w-full object-contain"
          />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-slate-400">
            Camera preview unavailable
          </div>
        )}
      </div>
    </div>
  );
}
