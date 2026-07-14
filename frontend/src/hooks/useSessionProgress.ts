import { useCallback, useEffect, useRef, useState } from "react";
import { getProgress } from "../api/sessionApi";
import { getBackendUrl, toWebSocketUrl } from "../utils/backendUrl";
import type { ProgressResponse, WebSocketMessage } from "../types/api";
import type { SessionStatus } from "../types/session";

type ProgressState = {
  status: SessionStatus | string;
  stage: string;
  progress: number;
  message: string;
};

export function useSessionProgress(sessionId: string | undefined, enabled = true) {
  const [progress, setProgress] = useState<ProgressState>({
    status: "PROCESSING",
    stage: "video_saved",
    progress: 0,
    message: "Waiting for processing to start.",
  });
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const applyUpdate = useCallback((update: Partial<ProgressState>) => {
    setProgress((prev) => ({ ...prev, ...update }));
  }, []);

  const poll = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data: ProgressResponse = await getProgress(sessionId);
      applyUpdate({
        status: data.status,
        stage: data.stage,
        progress: data.progress,
        message: data.message,
      });
    } catch {
      /* polling errors are non-fatal */
    }
  }, [sessionId, applyUpdate]);

  useEffect(() => {
    if (!enabled || !sessionId) return;

    const backendUrl = getBackendUrl();
    if (!backendUrl) return;

    let pollId: number | undefined;
    let closed = false;

    const startPolling = () => {
      poll();
      pollId = window.setInterval(poll, 2000);
    };

    try {
      const wsUrl = toWebSocketUrl(backendUrl, `/ws/sessions/${sessionId}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (closed) return;
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WebSocketMessage;
          applyUpdate({
            status: msg.status,
            ...(msg.stage !== undefined && { stage: msg.stage }),
            ...(msg.progress !== undefined && { progress: msg.progress }),
            ...(msg.message !== undefined && { message: msg.message }),
          });
        } catch {
          /* ignore malformed messages */
        }
      };

      ws.onerror = () => {
        setWsConnected(false);
        if (!pollId) startPolling();
      };

      ws.onclose = () => {
        setWsConnected(false);
        if (!pollId && !closed) startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      closed = true;
      if (pollId) window.clearInterval(pollId);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, sessionId, applyUpdate, poll]);

  return { progress, wsConnected, refresh: poll };
}
