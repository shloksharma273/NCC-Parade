import { getCameraStreamUrl } from "../api/cameraApi";

type CameraPreviewProps = {
  sessionId: string;
  active: boolean;
  label?: string;
  showAlignmentGuide?: boolean;
  /** Bump to force the MJPEG stream to reconnect (avoids frozen first frame). */
  streamKey?: number;
};

export function CameraPreview({
  sessionId,
  active,
  label = "Live Camera",
  showAlignmentGuide = false,
  streamKey = 0,
}: CameraPreviewProps) {
  const baseUrl = active ? getCameraStreamUrl(sessionId) : null;
  const streamUrl = baseUrl ? `${baseUrl}?v=${streamKey}` : null;

  return (
    <div className="command-card overflow-hidden">
      <div className="flex items-center justify-between bg-[var(--color-deep-olive)] px-4 py-2">
        <p className="text-sm font-medium text-white">{label}</p>
        {active && (
          <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-400" />
            Live
          </span>
        )}
      </div>

      <div className="relative aspect-video bg-black">
        {streamUrl ? (
          <>
            <img
              key={streamUrl}
              src={streamUrl}
              alt="Live camera preview"
              className="h-full w-full object-contain"
            />
            {showAlignmentGuide && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="h-[85%] w-[45%] rounded-lg border-2 border-dashed border-[var(--color-khaki)] opacity-80" />
                <p className="absolute bottom-3 left-0 right-0 text-center text-xs font-semibold uppercase tracking-wide text-[var(--color-sand)] drop-shadow">
                  Align full body within frame
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-slate-400">
            Camera preview unavailable
          </div>
        )}
      </div>
    </div>
  );
}
