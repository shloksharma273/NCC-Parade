import { useCallback, useEffect, useState } from "react";
import { getStatus } from "../api/statusApi";
import { parseApiError } from "../api/client";
import type { SystemStatus } from "../types/api";

export function useBackendStatus(refreshIntervalMs = 5000, enabled = true) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const data = await getStatus();
      setStatus(data);
    } catch (err) {
      setError(parseApiError(err));
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refresh();
    const id = window.setInterval(refresh, refreshIntervalMs);
    return () => window.clearInterval(id);
  }, [enabled, refresh, refreshIntervalMs]);

  const isReady =
    status?.backend_status === "ready" &&
    status.camera_connected &&
    status.model_ready &&
    status.storage_available;

  return { status, loading, error, refresh, isReady };
}
