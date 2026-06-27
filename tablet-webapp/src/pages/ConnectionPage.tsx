import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { checkHealth } from "../api/statusApi";
import { parseApiError } from "../api/client";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageLayout } from "../components/PageLayout";
import {
  clearBackendUrl,
  getBackendUrl,
  normalizeBackendUrl,
  setBackendUrl,
} from "../utils/backendUrl";

export function ConnectionPage() {
  const navigate = useNavigate();
  const saved = getBackendUrl() ?? "";
  const [url, setUrl] = useState(saved || "http://127.0.0.1:8000");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const connect = async (targetUrl: string) => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const normalized = normalizeBackendUrl(targetUrl);
      setBackendUrl(normalized);
      await checkHealth();
      setSuccess("Connected to PC backend successfully.");
      setTimeout(() => navigate("/dashboard"), 600);
    } catch (err) {
      clearBackendUrl();
      setError(
        parseApiError(err) ||
          "Could not connect to PC backend. Check IP address, Wi-Fi, and server status.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="Connect to PC Backend">
      <div className="mx-auto max-w-xl space-y-6">
        <p className="text-lg text-slate-600">
          Enter the PC backend URL. Both devices must be on the same Wi-Fi network.
        </p>

        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-slate-700">Backend URL</span>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://192.168.1.20:8000"
            className="w-full rounded-xl border border-slate-300 px-4 py-4 text-lg focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
          />
        </label>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {success && (
          <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-4 text-green-800">
            {success}
          </div>
        )}

        <PrimaryButton onClick={() => connect(url)} disabled={loading || !url.trim()}>
          {loading ? "Connecting..." : "Connect"}
        </PrimaryButton>

        {saved && (
          <PrimaryButton variant="secondary" onClick={() => connect(saved)} disabled={loading}>
            Use Saved Server
          </PrimaryButton>
        )}

        {saved && (
          <PrimaryButton
            variant="secondary"
            onClick={() => {
              clearBackendUrl();
              setUrl("http://127.0.0.1:8000");
              setSuccess(null);
              setError(null);
            }}
          >
            Clear Server
          </PrimaryButton>
        )}
      </div>
    </PageLayout>
  );
}
