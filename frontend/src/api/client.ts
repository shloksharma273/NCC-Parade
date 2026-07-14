import axios, { AxiosError } from "axios";
import { getBackendUrl } from "../utils/backendUrl";
import type { ApiError } from "../types/api";

export class BackendConnectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BackendConnectionError";
  }
}

export class ApiRequestError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
  }
}

export function getApiClient() {
  const baseURL = getBackendUrl();
  if (!baseURL) {
    throw new BackendConnectionError("No backend URL configured.");
  }

  const client = axios.create({
    baseURL,
    timeout: 30000,
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError<{ detail?: ApiError | string }>) => {
      if (!error.response) {
        throw new BackendConnectionError(
          "Unable to connect to the backend server. " +
          "If running on the same PC, ensure the backend is started and use http://127.0.0.1:8000. " +
          "If connecting from a tablet, ensure both devices are on the same network (Wi-Fi or Ethernet) and use the PC's LAN IP.",
        );
      }

      const detail = error.response.data?.detail;
      if (typeof detail === "object" && detail !== null && "message" in detail) {
        throw new ApiRequestError(detail.error ?? "API_ERROR", detail.message);
      }
      if (typeof detail === "string") {
        throw new ApiRequestError("API_ERROR", detail);
      }

      throw new ApiRequestError("API_ERROR", error.message || "Something went wrong. Please retry.");
    },
  );

  return client;
}

export function parseApiError(error: unknown): string {
  if (error instanceof BackendConnectionError || error instanceof ApiRequestError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please retry.";
}
