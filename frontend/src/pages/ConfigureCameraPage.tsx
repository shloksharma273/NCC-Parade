import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  deleteCameraConfig,
  fetchCameraConfig,
  saveCameraConfig,
  testCameraConfig,
} from "../api/cameraApi";
import type { CameraConfigEntry, CameraConfigTest } from "../api/cameraApi";
import { parseApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { PageLayout } from "../components/PageLayout";
import { PrimaryButton } from "../components/PrimaryButton";
import { getBackendUrl } from "../utils/backendUrl";

type FormState = {
  slug: string;
  label: string;
  host: string;
  port: string;
  username: string;
  password: string;
  mainPath: string;
  subPath: string;
};

const BLANK_FORM: FormState = {
  slug: "",
  label: "",
  host: "",
  port: "554",
  username: "admin",
  password: "",
  mainPath: "",
  subPath: "",
};

function formFor(camera: CameraConfigEntry): FormState {
  return {
    slug: camera.slug,
    label: camera.label,
    host: camera.host,
    port: String(camera.port),
    // The server sends a masked placeholder for a stored password; submitting it
    // unchanged tells the server to keep what it already has.
    username: camera.username || "admin",
    password: camera.password,
    mainPath: "",
    subPath: "",
  };
}

/** Turn a test/save outcome code into advice the operator can act on. */
function guidanceFor(outcome: string): string | null {
  switch (outcome) {
    case "bad_credentials":
    case "BAD_CREDENTIALS":
      return "Check the username and password you use to log into the camera's own web page.";
    case "no_response":
    case "NO_RESPONSE":
      return "The camera did not answer. Verify the IP address, that it is powered on, and that its network cable is connected.";
    case "path_not_found":
    case "PATH_NOT_FOUND":
      return "The login worked but the stream path did not. Enter the RTSP path from the camera's manual under Advanced.";
    default:
      return null;
  }
}

const INPUT_CLASS =
  "w-full rounded-xl border-2 border-[var(--color-khaki)] px-4 py-3 text-lg";

export function ConfigureCameraPage() {
  const navigate = useNavigate();
  const backend = getBackendUrl();

  const [cameras, setCameras] = useState<CameraConfigEntry[]>([]);
  const [configPath, setConfigPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(BLANK_FORM);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<CameraConfigTest | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchCameraConfig();
      setCameras(data.cameras);
      setConfigPath(data.config_path);
      setError(null);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!backend) {
      navigate("/connect", { replace: true });
      return;
    }
    load();
  }, [backend, navigate, load]);

  const set = (key: keyof FormState) => (value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const beginEdit = (camera: CameraConfigEntry) => {
    setEditing(camera.slug);
    setForm(formFor(camera));
    setTestResult(null);
    setNotice(null);
    setShowAdvanced(false);
  };

  const beginAdd = () => {
    setEditing("__new__");
    setForm(BLANK_FORM);
    setTestResult(null);
    setNotice(null);
    setShowAdvanced(false);
  };

  const closeForm = () => {
    setEditing(null);
    setTestResult(null);
  };

  const payload = () => ({
    slug: editing === "__new__" ? undefined : form.slug,
    label: form.label || undefined,
    host: form.host.trim(),
    port: Number(form.port) || 554,
    username: form.username.trim(),
    password: form.password,
    main_path: form.mainPath.trim() || null,
    sub_path: form.subPath.trim() || null,
  });

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    setNotice(null);
    try {
      setTestResult(await testCameraConfig(payload()));
    } catch (err) {
      setTestResult({
        success: false,
        outcome: "error",
        message: parseApiError(err),
        main_path: null,
        sub_path: null,
        detected_family: null,
      });
    } finally {
      setTesting(false);
    }
  };

  const runSave = async (verify: boolean) => {
    setSaving(true);
    setNotice(null);
    try {
      const result = await saveCameraConfig({ ...payload(), verify });
      setNotice(result.message);
      setTestResult(null);
      closeForm();
      await load();
    } catch (err) {
      setTestResult({
        success: false,
        outcome: "error",
        message: parseApiError(err),
        main_path: null,
        sub_path: null,
        detected_family: null,
      });
    } finally {
      setSaving(false);
    }
  };

  const runDelete = async (slug: string) => {
    setSaving(true);
    try {
      await deleteCameraConfig(slug);
      setNotice("Camera removed.");
      closeForm();
      await load();
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Configure Camera" strip="Admin Mode" backTo="/admin">
        <LoadingState message="Reading camera configuration..." />
      </PageLayout>
    );
  }

  const busy = testing || saving;
  const guidance = testResult ? guidanceFor(testResult.outcome) : null;

  return (
    <PageLayout
      title="Configure Camera"
      strip="Admin Mode"
      subtitle="IP camera credentials and stream settings"
      backTo="/admin"
    >
      <div className="mx-auto max-w-2xl space-y-5">
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        {notice && (
          <div className="command-card border-[var(--color-success)] p-4">
            <p className="font-semibold text-[var(--color-success)]">{notice}</p>
          </div>
        )}

        {cameras.length === 0 && !editing && (
          <div className="command-card p-5 text-sm text-slate-600">
            No IP cameras are configured yet. Add one to record from a network camera;
            USB cameras work without any configuration.
          </div>
        )}

        {cameras.map((camera) => (
          <div key={camera.slug} className="command-card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-command text-lg font-bold">{camera.label}</p>
                <p className="font-mono text-xs text-slate-500">
                  {camera.host}:{camera.port} · {camera.device_id}
                </p>
              </div>
              <span
                className={`rounded px-2 py-1 text-xs font-bold uppercase ${
                  camera.available
                    ? "bg-[var(--color-success)] text-white"
                    : "bg-[var(--color-fail)] text-white"
                }`}
              >
                {camera.available ? "Ready" : camera.status}
              </span>
            </div>

            <p className="mt-2 text-sm text-slate-600">{camera.message}</p>

            <p className="mt-2 text-sm">
              <span className="font-semibold">Password: </span>
              {camera.password_set ? (
                <span className="text-[var(--color-success)]">set</span>
              ) : (
                <span className="text-[var(--color-fail)]">not set — the camera will reject the connection</span>
              )}
            </p>

            {editing !== camera.slug && (
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => beginEdit(camera)}
                  className="rounded-lg border-2 border-[var(--color-army-green)] px-4 py-2 font-semibold hover:bg-[var(--color-sand)]"
                >
                  Edit credentials
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => runDelete(camera.slug)}
                  className="rounded-lg border-2 border-[var(--color-fail)] px-4 py-2 font-semibold text-[var(--color-fail)] hover:bg-red-50 disabled:opacity-50"
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        ))}

        {editing && (
          <form
            className="command-card space-y-4 p-5"
            onSubmit={(e) => {
              e.preventDefault();
              runSave(true);
            }}
          >
            <p className="font-command text-xl font-bold">
              {editing === "__new__" ? "Add IP Camera" : "Edit Camera"}
            </p>

            <label className="block">
              <span className="mb-2 block font-semibold">Name</span>
              <input
                value={form.label}
                onChange={(e) => set("label")(e.target.value)}
                placeholder="Parade Ground Front"
                className={INPUT_CLASS}
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-3">
              <label className="block sm:col-span-2">
                <span className="mb-2 block font-semibold">Camera IP address *</span>
                <input
                  value={form.host}
                  onChange={(e) => set("host")(e.target.value)}
                  required
                  placeholder="192.168.1.50"
                  className={INPUT_CLASS}
                />
              </label>
              <label className="block">
                <span className="mb-2 block font-semibold">RTSP port</span>
                <input
                  value={form.port}
                  onChange={(e) => set("port")(e.target.value)}
                  inputMode="numeric"
                  className={INPUT_CLASS}
                />
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block font-semibold">Username *</span>
                <input
                  value={form.username}
                  onChange={(e) => set("username")(e.target.value)}
                  required
                  autoComplete="off"
                  className={INPUT_CLASS}
                />
              </label>
              <label className="block">
                <span className="mb-2 block font-semibold">Password *</span>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => set("password")(e.target.value)}
                  autoComplete="new-password"
                  placeholder="Camera password"
                  className={INPUT_CLASS}
                />
              </label>
            </div>

            <p className="text-xs text-slate-500">
              Use the same username and password you use to log into the camera's own
              web page. Leaving the password unchanged keeps the one already stored.
            </p>

            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-sm font-semibold underline"
            >
              {showAdvanced ? "Hide" : "Show"} advanced stream paths
            </button>

            {showAdvanced && (
              <div className="space-y-4 rounded-xl bg-[var(--color-sand)] p-4">
                <p className="text-xs text-slate-600">
                  Leave these blank and the stream path is detected automatically.
                  Fill them in only if detection fails — the paths are in the camera's
                  manual.
                </p>
                <label className="block">
                  <span className="mb-2 block font-semibold">Main stream path</span>
                  <input
                    value={form.mainPath}
                    onChange={(e) => set("mainPath")(e.target.value)}
                    placeholder="cam/realmonitor?channel=1&subtype=0"
                    className={INPUT_CLASS}
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block font-semibold">Sub stream path</span>
                  <input
                    value={form.subPath}
                    onChange={(e) => set("subPath")(e.target.value)}
                    placeholder="cam/realmonitor?channel=1&subtype=1"
                    className={INPUT_CLASS}
                  />
                </label>
              </div>
            )}

            {testResult && (
              <div
                className={`rounded-xl border-2 p-4 ${
                  testResult.success
                    ? "border-[var(--color-success)] bg-green-50"
                    : "border-[var(--color-fail)] bg-red-50"
                }`}
              >
                <p
                  className={`font-semibold ${
                    testResult.success
                      ? "text-[var(--color-success)]"
                      : "text-[var(--color-fail)]"
                  }`}
                >
                  {testResult.success ? "✓ Connected" : "✕ Could not connect"}
                </p>
                <p className="mt-1 text-sm text-slate-700">{testResult.message}</p>
                {guidance && <p className="mt-2 text-sm text-slate-600">{guidance}</p>}
                {testResult.main_path && (
                  <p className="mt-2 font-mono text-xs text-slate-600">
                    main: {testResult.main_path}
                    {testResult.sub_path ? ` · sub: ${testResult.sub_path}` : ""}
                  </p>
                )}
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={runTest}
                disabled={busy || !form.host.trim()}
                className="rounded-xl border-2 border-[var(--color-army-green)] px-4 py-3 text-lg font-semibold hover:bg-[var(--color-sand)] disabled:opacity-50"
              >
                {testing ? "Testing..." : "Test Connection"}
              </button>
              <PrimaryButton type="submit" disabled={busy || !form.host.trim()}>
                {saving ? "Saving..." : "Test & Save"}
              </PrimaryButton>
            </div>

            {testResult && !testResult.success && (
              <button
                type="button"
                onClick={() => runSave(false)}
                disabled={busy || !form.mainPath.trim()}
                className="w-full rounded-xl border-2 border-dashed border-slate-400 px-4 py-2 text-sm font-semibold text-slate-600 disabled:opacity-40"
              >
                Save anyway without testing (needs a main stream path)
              </button>
            )}

            <button
              type="button"
              onClick={closeForm}
              className="w-full py-2 text-sm font-semibold underline"
            >
              Cancel
            </button>
          </form>
        )}

        {!editing && (
          <PrimaryButton variant="secondary" onClick={beginAdd}>
            Add IP Camera
          </PrimaryButton>
        )}

        <p className="text-xs text-slate-500">
          Saved to <span className="font-mono">{configPath}</span> on the server. The
          password is stored there in plain text, as the camera requires it to
          connect — keep access to that PC restricted.
        </p>
      </div>
    </PageLayout>
  );
}
