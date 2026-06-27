import { Navigate, Route, Routes } from "react-router-dom";
import { getBackendUrl } from "./utils/backendUrl";
import { SessionProvider } from "./hooks/useSessionState";
import { ConnectionPage } from "./pages/ConnectionPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NewSessionPage } from "./pages/NewSessionPage";
import { RecordingPage } from "./pages/RecordingPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ReportPage } from "./pages/ReportPage";
import { RecentSessionsPage } from "./pages/RecentSessionsPage";

function RequireBackend({ children }: { children: React.ReactNode }) {
  if (!getBackendUrl()) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route path="/" element={<ConnectionPage />} />
        <Route
          path="/dashboard"
          element={
            <RequireBackend>
              <DashboardPage />
            </RequireBackend>
          }
        />
        <Route
          path="/sessions/new"
          element={
            <RequireBackend>
              <NewSessionPage />
            </RequireBackend>
          }
        />
        <Route
          path="/sessions/recent"
          element={
            <RequireBackend>
              <RecentSessionsPage />
            </RequireBackend>
          }
        />
        <Route
          path="/sessions/:sessionId/recording"
          element={
            <RequireBackend>
              <RecordingPage />
            </RequireBackend>
          }
        />
        <Route
          path="/sessions/:sessionId/processing"
          element={
            <RequireBackend>
              <ProcessingPage />
            </RequireBackend>
          }
        />
        <Route
          path="/sessions/:sessionId/report"
          element={
            <RequireBackend>
              <ReportPage />
            </RequireBackend>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SessionProvider>
  );
}
