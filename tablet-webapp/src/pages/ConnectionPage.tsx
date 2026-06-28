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
  const defaultBackendUrl =
    typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
      ? `http://${window.location.hostname}:8000`
      : "http://127.0.0.1:8000";
  const [url, setUrl] = useState(saved || defaultBackendUrl);
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
      setSuccess("Connected to drill server.");
      setTimeout(() => navigate("/dashboard"), 600);
    } catch (err) {
      clearBackendUrl();
      setError(
        parseApiError(err) ||
          "Unable to connect. Check that tablet and PC are on the same Wi-Fi.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="Connect to Drill Server" strip="Setup" subtitle="Manual connection fallback">
      <div className="command-card mx-auto max-w-xl space-y-6 p-6">
        <p className="text-lg">
          Scan the QR code on the PC for automatic pairing. Use this screen only if manual connection is needed.
        </p>
        <p className="rounded-xl border-2 border-[var(--color-warning)] bg-[var(--color-sand)] px-4 py-3 text-sm">
          On a tablet, do not use <code className="font-mono">127.0.0.1</code> or{" "}
          <code className="font-mono">localhost</code>. Use your PC&apos;s Wi-Fi IP, for example{" "}
          <code className="font-mono">http://192.168.29.42:8000</code>.
        </p>

        <label className="block">
          <span className="mb-2 block font-semibold">Backend URL</span>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://192.168.1.20:8000"
            className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg focus:border-[var(--color-army-green)] focus:outline-none"
          />
        </label>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {success && (
          <div className="rounded-xl border-2 border-[var(--color-success)] bg-green-50 px-4 py-4 text-[var(--color-success)]">
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
              setUrl(defaultBackendUrl);
              setSuccess(null);
              setError(null);
            }}
          >
            Clear Saved Server
          </PrimaryButton>
        )}
      </div>
    </PageLayout>
  );
}
