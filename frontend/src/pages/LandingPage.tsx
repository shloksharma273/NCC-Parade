import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { checkHealth } from "../api/statusApi";
import { parseApiError } from "../api/client";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { ErrorBanner } from "../components/ErrorBanner";
import { applyPairingFromSearch, getBackendUrl, normalizeBackendUrl, setBackendUrl } from "../utils/backendUrl";

export function LandingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<"connecting" | "ok" | "error">("connecting");
  const [message, setMessage] = useState("Connecting to drill server...");
  const [backend, setBackend] = useState<string | null>(null);

  useEffect(() => {
    const connect = async () => {
      const fromQr = applyPairingFromSearch(searchParams.toString());
      const target = fromQr ? getBackendUrl() : getBackendUrl();
      if (!target) {
        setStatus("error");
        setMessage("No backend configured. Scan the PC QR code or connect manually.");
        return;
      }
      setBackend(target);
      try {
        setBackendUrl(normalizeBackendUrl(target));
        await checkHealth();
        setStatus("ok");
        setTimeout(() => navigate("/dashboard", { replace: true }), 600);
      } catch (err) {
        setStatus("error");
        setMessage(parseApiError(err));
      }
    };
    connect();
  }, [navigate, searchParams]);

  return (
    <PageLayout title="Drill Recognition Console" strip="Operational Mode" subtitle="Tablet Control Panel">
      <div className="command-card mx-auto max-w-lg p-8 text-center">
        {status === "connecting" && <LoadingState message={message} />}
        {status === "ok" && <p className="text-lg text-[var(--color-success)] font-semibold">Connected. Opening dashboard...</p>}
        {status === "error" && (
          <>
            <ErrorBanner message={message} />
            {backend && <p className="mt-4 text-sm text-slate-600">Backend: {backend}</p>}
            <div className="mt-6 grid gap-3">
              <PrimaryButton onClick={() => navigate("/connect")}>Manual Connection</PrimaryButton>
            </div>
          </>
        )}
      </div>
    </PageLayout>
  );
}
