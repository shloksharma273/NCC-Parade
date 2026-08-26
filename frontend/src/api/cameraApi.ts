import { getApiClient } from "./client";
import type { SessionActionResponse } from "../types/api";
import { getBackendUrl } from "../utils/backendUrl";

export type CameraDiagnostics = {
  camera_type: string;
  camera_host: string | null;
  rtsp_port: number | null;
  main_stream_configured: boolean;
  sub_stream_configured: boolean;
  main_stream_openable: boolean;
  sub_stream_openable: boolean;
  last_checked_at: string;
  message: string;
};

export async function startCameraPreview(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(
    `/sessions/${sessionId}/camera/preview/start`,
  );
  return data;
}

export async function stopCameraPreview(sessionId: string): Promise<SessionActionResponse> {
  const client = getApiClient();
  const { data } = await client.post<SessionActionResponse>(
    `/sessions/${sessionId}/camera/preview/stop`,
  );
  return data;
}

export async function fetchCameraDiagnostics(): Promise<CameraDiagnostics> {
  const client = getApiClient();
  const { data } = await client.get<CameraDiagnostics>("/camera/diagnostics");
  return data;
}

export function getCameraStreamUrl(sessionId: string): string | null {
  const backendUrl = getBackendUrl();
  if (!backendUrl) return null;
  return `${backendUrl}/sessions/${sessionId}/camera/stream`;
}

export function getCameraSnapshotUrl(): string | null {
  const backend = getBackendUrl();
  if (!backend) return null;
  return `${backend}/camera/snapshot?t=${Date.now()}`;
}

export type CameraDeviceKind = "usb" | "ip";
export type CameraDeviceStatus =
  | "ready"
  | "unreachable"
  | "unauthorized"
  | "unconfigured"
  | "detected";

export type CameraDevice = {
  device_id: string;
  kind: CameraDeviceKind;
  label: string;
  status: CameraDeviceStatus;
  available: boolean;
  message: string;
  index: number | null;
  host: string | null;
  port: number | null;
  has_sub_stream: boolean;
  capabilities: { width?: number; height?: number };
  warm: boolean;
  /** Live preview state for this device: "opening" | "streaming" | "failed". */
  preview_state: string | null;
  preview_error: string | null;
};

export type CameraDeviceList = {
  devices: CameraDevice[];
  default_device_id: string | null;
  available_count: number;
  message: string;
};

export type CameraWarmup = {
  warmed: string[];
  skipped: boolean;
  message: string;
};

export async function fetchCameraDevices(refresh = false): Promise<CameraDeviceList> {
  const client = getApiClient();
  const { data } = await client.get<CameraDeviceList>("/camera/devices", {
    params: refresh ? { refresh: true } : undefined,
    // A forced rescan opens every USB index, so allow longer than the default.
    timeout: refresh ? 60000 : 30000,
  });
  return data;
}

/**
 * Open every reachable camera ahead of time so the chooser screen has frames
 * ready. Fire-and-forget: the backend warms each device on its own thread and
 * closes any camera nobody asks about, so a failure here is never fatal.
 */
export async function warmupCameras(): Promise<CameraWarmup | null> {
  try {
    const client = getApiClient();
    const { data } = await client.post<CameraWarmup>("/camera/warmup");
    return data;
  } catch {
    return null;
  }
}

export async function startDevicePreview(deviceId: string): Promise<CameraWarmup> {
  const client = getApiClient();
  const { data } = await client.post<CameraWarmup>(
    `/camera/devices/${encodeURIComponent(deviceId)}/preview/start`,
  );
  return data;
}

export async function stopDevicePreview(deviceId: string): Promise<void> {
  const client = getApiClient();
  await client.post(`/camera/devices/${encodeURIComponent(deviceId)}/preview/stop`);
}

/**
 * Still-frame URL for one device. The chooser grid polls this per tile instead
 * of opening an MJPEG stream each, because browsers cap concurrent connections
 * per host and a grid of never-ending streams would starve the page's own
 * API calls. `cacheBuster` should change on every poll.
 */
export function getDeviceSnapshotUrl(deviceId: string, cacheBuster: number): string | null {
  const backend = getBackendUrl();
  if (!backend) return null;
  return `${backend}/camera/devices/${encodeURIComponent(deviceId)}/snapshot?t=${cacheBuster}`;
}

export function getDeviceStreamUrl(deviceId: string): string | null {
  const backend = getBackendUrl();
  if (!backend) return null;
  return `${backend}/camera/devices/${encodeURIComponent(deviceId)}/stream`;
}

// ── Camera configuration ───────────────────────────────────────────────────

export type CameraConfigEntry = {
  slug: string;
  device_id: string;
  label: string;
  host: string;
  port: number;
  username: string;
  password_set: boolean;
  /** Always masked by the server; the real password is never sent back. */
  password: string;
  main_url: string;
  sub_url: string;
  status: string;
  message: string;
  available: boolean;
};

export type CameraConfigList = {
  cameras: CameraConfigEntry[];
  config_path: string;
  config_exists: boolean;
  message: string;
};

export type CameraConfigTest = {
  success: boolean;
  outcome: string;
  message: string;
  main_path: string | null;
  sub_path: string | null;
  detected_family: string | null;
};

export type CameraConfigSave = {
  slug: string;
  device_id: string;
  saved: boolean;
  detected_family: string | null;
  status: string;
  message: string;
};

export type CameraConfigInput = {
  slug?: string;
  label?: string;
  host: string;
  port: number;
  username: string;
  password: string;
  main_path?: string | null;
  sub_path?: string | null;
  verify?: boolean;
};

export async function fetchCameraConfig(): Promise<CameraConfigList> {
  const client = getApiClient();
  const { data } = await client.get<CameraConfigList>("/camera/config");
  return data;
}

/** Check credentials against the camera without saving. Probing several stream
 *  paths can take a while, so this allows longer than the default timeout. */
export async function testCameraConfig(input: CameraConfigInput): Promise<CameraConfigTest> {
  const client = getApiClient();
  const { data } = await client.post<CameraConfigTest>("/camera/config/test", input, {
    timeout: 90000,
  });
  return data;
}

export async function saveCameraConfig(input: CameraConfigInput): Promise<CameraConfigSave> {
  const client = getApiClient();
  const { data } = await client.put<CameraConfigSave>("/camera/config", input, {
    timeout: 90000,
  });
  return data;
}

export async function deleteCameraConfig(slug: string): Promise<void> {
  const client = getApiClient();
  await client.delete(`/camera/config/${encodeURIComponent(slug)}`);
}
