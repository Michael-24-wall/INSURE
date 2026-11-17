import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Settings as SettingsIcon, SlidersHorizontal } from "lucide-react";
import api, { getErrorMessage } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { titleize } from "../../lib/format";
import { Alert, Button, Input, Modal, PageLoader, PageHeader, Textarea } from "../../components/ui";

const KNOWN_SETTINGS = {
  platform_name: { label: "Platform name", description: "Public brand shown across the marketplace.", type: "text" },
  marketplace_open: { label: "Marketplace open", description: "Allow customers to submit new quotation requests.", type: "boolean" },
};

function displayValue(value) {
  if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

export default function AdminSettings() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [values, setValues] = useState({});
  const [modal, setModal] = useState(false);
  const [newSetting, setNewSetting] = useState({ key: "", value: "", description: "" });
  const [error, setError] = useState("");
  const [initialised, setInitialised] = useState(false);

  const settings = useQuery({
    queryKey: ["platform-settings"],
    queryFn: async () => (await api.get("/admin/settings/")).data,
  });

  useEffect(() => {
    if (settings.data && !initialised) {
      setValues(settings.data);
      setInitialised(true);
    }
  }, [settings.data, initialised]);

  const save = useMutation({
    mutationFn: async ({ key, value, description }) => (await api.put("/admin/settings/", { key, value, description })).data,
    onSuccess: (data) => {
      setValues((current) => ({ ...current, [data.key]: data.value }));
      queryClient.invalidateQueries({ queryKey: ["platform-settings"] });
      toast.push("Setting saved.", "success");
      setModal(false);
      setNewSetting({ key: "", value: "", description: "" });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const entries = useMemo(() => Object.entries(values).sort(([a], [b]) => a.localeCompare(b)), [values]);

  if (settings.isLoading) return <PageLoader />;
  if (settings.isError) return <Alert>Could not load platform settings.</Alert>;

  function saveValue(key, value) {
    setError("");
    const meta = KNOWN_SETTINGS[key];
    save.mutate({ key, value, description: meta?.description || "" });
  }

  function updateKnown(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submitNew(event) {
    event.preventDefault();
    setError("");
    if (!newSetting.key.trim()) {
      setError("A setting key is required.");
      return;
    }
    let parsed = newSetting.value;
    try {
      parsed = JSON.parse(newSetting.value);
    } catch {
      parsed = newSetting.value;
    }
    save.mutate({ key: newSetting.key.trim(), value: parsed, description: newSetting.description });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Platform administration"
        title="Settings"
        description="Control marketplace behaviour and platform-wide configuration."
        actions={<Button icon={Plus} onClick={() => { setError(""); setModal(true); }}>Add setting</Button>}
      />

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          {entries.map(([key, value]) => {
            const meta = KNOWN_SETTINGS[key];
            return (
              <div key={key} className="surface p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-display text-base font-bold text-ink-950">{meta?.label || titleize(key)}</p>
                    <p className="mt-1 text-xs text-ink-400">{meta?.description || "Custom platform setting."}</p>
                    <p className="mt-1 font-mono text-[10px] text-ink-300">{key}</p>
                  </div>
                  {meta?.type !== "boolean" && <Button size="sm" icon={Save} onClick={() => saveValue(key, values[key])} loading={save.isPending}>Save</Button>}
                </div>
                <div className="mt-4">
                  {meta?.type === "boolean" ? (
                    <div className="flex items-center justify-between rounded-xl bg-ink-50 p-3">
                      <div>
                        <p className="text-sm font-semibold text-ink-900">{value ? "Marketplace is open" : "Marketplace is closed"}</p>
                        <p className="mt-0.5 text-xs text-ink-400">Currently {value ? "accepting" : "rejecting"} new quotation requests.</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => { updateKnown(key, !value); saveValue(key, !value); }}
                        className={`relative h-6 w-11 rounded-full transition ${value ? "bg-brand-600" : "bg-ink-300"}`}
                        aria-label="Toggle setting"
                      >
                        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${value ? "left-[22px]" : "left-0.5"}`} />
                      </button>
                    </div>
                  ) : (
                    <Input value={displayValue(value)} onChange={(event) => updateKnown(key, event.target.value)} />
                  )}
                </div>
              </div>
            );
          })}
          {!entries.length && <div className="surface p-10 text-center"><SettingsIcon className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No settings defined</p></div>}
        </div>

        <div className="space-y-4">
          <div className="surface p-5">
            <div className="flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-brand-700" /><h2 className="font-display text-base font-bold text-ink-950">Configuration notes</h2></div>
            <ul className="mt-4 space-y-3 text-xs leading-relaxed text-ink-500">
              <li>Settings apply immediately across API and clients.</li>
              <li>Boolean values accept <code className="rounded bg-ink-100 px-1">true</code> or <code className="rounded bg-ink-100 px-1">false</code>; use the toggle for known flags.</li>
              <li>Only platform administrators can modify settings. Every change is recorded in the audit log.</li>
              <li>Closing the marketplace does not affect existing quotes, applications or policies.</li>
            </ul>
          </div>
          <div className="surface p-5">
            <h2 className="font-display text-base font-bold text-ink-950">Danger zone</h2>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">Destructive maintenance operations are intentionally not exposed through this interface. Use management commands with an audited change request instead.</p>
          </div>
        </div>
      </div>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Add platform setting"
        description="Values are stored as JSON where possible."
        footer={<><Button variant="secondary" onClick={() => setModal(false)}>Cancel</Button><Button onClick={submitNew} loading={save.isPending} icon={Plus}>Save setting</Button></>}
      >
        <form onSubmit={submitNew} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Key" required value={newSetting.key} onChange={(event) => setNewSetting((current) => ({ ...current, key: event.target.value }))} placeholder="e.g. support_email" />
          <Textarea label="Value" required value={newSetting.value} onChange={(event) => setNewSetting((current) => ({ ...current, value: event.target.value }))} placeholder='e.g. "support@example.com" or true' />
          <Input label="Description" value={newSetting.description} onChange={(event) => setNewSetting((current) => ({ ...current, description: event.target.value }))} />
        </form>
      </Modal>
    </div>
  );
}
