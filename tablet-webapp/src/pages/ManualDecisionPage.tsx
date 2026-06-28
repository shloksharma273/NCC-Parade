import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { saveDecision } from "../api/decisionApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";

const DECISIONS = [
  { value: "accept_ai", label: "Accept AI Result" },
  { value: "pass", label: "Mark as Pass" },
  { value: "needs_correction", label: "Mark as Needs Correction" },
  { value: "fail", label: "Mark as Fail" },
  { value: "needs_human_review", label: "Needs Human Review" },
] as const;

export function ManualDecisionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [decision, setDecision] = useState<string>("accept_ai");
  const [remarks, setRemarks] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      await saveDecision(sessionId, {
        decision: decision as (typeof DECISIONS)[number]["value"],
        remarks: remarks.trim() || undefined,
      });
      navigate(`/sessions/${sessionId}/report`);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout title="Manual Decision" strip="Instructor Override" backTo={`/sessions/${sessionId}/report`}>
      <div className="command-card mx-auto max-w-xl space-y-5 p-6">
        {error && <ErrorBanner message={error} />}
        <label className="block">
          <span className="mb-2 block font-semibold">Decision</span>
          <select
            value={decision}
            onChange={(e) => setDecision(e.target.value)}
            className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-4 text-lg"
          >
            {DECISIONS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block font-semibold">Instructor Remarks</span>
          <textarea
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            rows={4}
            placeholder="Required when overriding AI result..."
            className="w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-3"
          />
        </label>
        <PrimaryButton onClick={submit} disabled={loading}>
          {loading ? "Saving..." : "Save Decision"}
        </PrimaryButton>
      </div>
    </PageLayout>
  );
}
