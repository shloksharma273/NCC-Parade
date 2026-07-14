import { Navigate, Route, Routes } from "react-router-dom";
import { getBackendUrl } from "./utils/backendUrl";
import { SessionProvider } from "./hooks/useSessionState";
import { LandingPage } from "./pages/LandingPage";
import { ConnectionPage } from "./pages/ConnectionPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NewSessionPage } from "./pages/NewSessionPage";
import { ReadinessCheckPage } from "./pages/ReadinessCheckPage";
import { RecordingPage } from "./pages/RecordingPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ReportPage } from "./pages/ReportPage";
import { DetailedReportPage } from "./pages/DetailedReportPage";
import { ManualDecisionPage } from "./pages/ManualDecisionPage";
import { AttemptHistoryPage } from "./pages/AttemptHistoryPage";
import { RecentSessionsPage } from "./pages/RecentSessionsPage";
import { AdminStatusPage } from "./pages/AdminStatusPage";

function RequireBackend({ children }: { children: React.ReactNode }) {
  if (!getBackendUrl()) {
    return <Navigate to="/connect" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/connect" element={<ConnectionPage />} />
        <Route
          path="/dashboard"
          element={
            <RequireBackend>
              <DashboardPage />
            </RequireBackend>
          }
        />
        <Route path="/admin" element={<RequireBackend><AdminStatusPage /></RequireBackend>} />
        <Route path="/sessions/new" element={<RequireBackend><NewSessionPage /></RequireBackend>} />
        <Route path="/sessions/recent" element={<RequireBackend><RecentSessionsPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/readiness" element={<RequireBackend><ReadinessCheckPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/recording" element={<RequireBackend><RecordingPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/processing" element={<RequireBackend><ProcessingPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/report" element={<RequireBackend><ReportPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/report/detailed" element={<RequireBackend><DetailedReportPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/decision" element={<RequireBackend><ManualDecisionPage /></RequireBackend>} />
        <Route path="/sessions/:sessionId/attempts" element={<RequireBackend><AttemptHistoryPage /></RequireBackend>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SessionProvider>
  );
}
