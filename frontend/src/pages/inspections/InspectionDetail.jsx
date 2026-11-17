import { lazy, Suspense, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Bot, Camera, CheckCircle2, MapPin, Play, Plus, ShieldCheck, Trash2, Wrench } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { INSPECTION_ZONES } from "../../lib/constants";
import { formatDate, formatDateTime, titleize } from "../../lib/format";
import { Alert, Button, Input, Modal, PageLoader, Select, StatusBadge, Textarea } from "../../components/ui";
import { DetailItem } from "../../components/DataTable";
import FileDownload from "../../components/FileDownload";

const VehicleScene = lazy(() => import("../../components/VehicleScene"));

const SEVERITIES = [
  { value: "minor", label: "Minor" },
  { value: "moderate", label: "Moderate" },
  { value: "severe", label: "Severe" },
];

const CONDITIONS = [
  { value: "excellent", label: "Excellent" },
  { value: "good", label: "Good" },
  { value: "fair", label: "Fair" },
  { value: "poor", label: "Poor" },
];

export default function InspectionDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [selectedZone, setSelectedZone] = useState("");
  const [damageForm, setDamageForm] = useState({ zone: "", severity: "minor", description: "", estimated_repair_cost: "", photo: null });
  const [scheduleForm, setScheduleForm] = useState({ inspector: "", scheduled_at: "", location: "" });
  const [completeForm, setCompleteForm] = useState({ report_summary: "", overall_condition: "good", report_file: null });
  const [aiFile, setAiFile] = useState(null);
  const [aiResult, setAiResult] = useState(null);

  const query = useQuery({
    queryKey: ["inspection", id],
    queryFn: async () => (await api.get(`/inspections/${id}/`)).data,
  });
  const inspection = query.data;
  const orgId = user?.memberships?.[0]?.organization_id;
  const isAdmin = ["admin", "super_admin"].includes(user?.role);
  const isProvider = ["provider_admin", "provider_staff", "claims_officer"].includes(user?.role);

  const members = useQuery({
    queryKey: ["organization-members", orgId],
    queryFn: async () => (await api.get(`/organizations/${orgId}/members/`)).data,
    enabled: Boolean(orgId) && isProvider,
  });
  const adminInspectors = useQuery({
    queryKey: ["inspectors", "admin"],
    queryFn: async () => (await api.get("/auth/users/?role=inspector&page_size=100")).data,
    enabled: isAdmin,
  });

  const inspectorOptions = isAdmin ? listData(adminInspectors.data).map((inspector) => ({ value: inspector.id, label: inspector.full_name || inspector.email })) : listData(members.data).filter((member) => member.user_role === "inspector" || member.role === "inspector").map((member) => ({ value: member.user, label: member.user_name }));

  const canEdit = useMemo(() => Boolean(inspection) && (isAdmin || (user?.id === inspection.inspector && inspection.status === "in_progress")), [inspection, isAdmin, user?.id]);
  const canSchedule = useMemo(() => Boolean(inspection) && inspection.status === "requested" && (isProvider || isAdmin), [inspection, isProvider, isAdmin]);
  const canComplete = useMemo(() => Boolean(inspection) && ["scheduled", "in_progress"].includes(inspection.status) && (isAdmin || user?.id === inspection.inspector), [inspection, isAdmin, user?.id]);

  const action = useMutation({
    mutationFn: async ({ key, formData, json }) => (await api.post(`/inspections/${id}/${key}/`, formData || json, formData ? { headers: { "Content-Type": "multipart/form-data" } } : undefined)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inspection", id] });
      queryClient.invalidateQueries({ queryKey: ["inspections"] });
      toast.push("Inspection updated.", "success");
      setModal(null);
      setSelectedZone("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const addDamage = useMutation({
    mutationFn: async () => {
      const body = new FormData();
      body.append("zone", damageForm.zone);
      body.append("severity", damageForm.severity);
      body.append("description", damageForm.description);
      body.append("estimated_repair_cost", damageForm.estimated_repair_cost || 0);
      if (damageForm.photo) body.append("photo", damageForm.photo);
      return (await api.post(`/inspections/${id}/damages/`, body)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inspection", id] });
      toast.push("Damage recorded.", "success");
      setModal(null);
      setSelectedZone("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const deleteDamage = useMutation({
    mutationFn: async (damageId) => api.delete(`/inspections/${id}/damages/${damageId}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inspection", id] });
      toast.push("Damage removed.", "success");
    },
    onError: (err) => toast.push(getErrorMessage(err), "error"),
  });

  const aiAssist = useMutation({
    mutationFn: async () => {
      const body = new FormData();
      body.append("image", aiFile);
      return (await api.post(`/inspections/${id}/ai-assist/`, body)).data;
    },
    onSuccess: (data) => setAiResult(data),
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (query.isLoading) return <PageLoader />;
  if (query.isError) return <Alert>Could not load this inspection.</Alert>;

  function openDamage(zone) {
    setError("");
    setDamageForm({ zone, severity: "minor", description: "", estimated_repair_cost: "", photo: null });
    setSelectedZone(zone);
    setModal("damage");
  }

  function openSchedule() {
    setError("");
    setScheduleForm({ inspector: "", scheduled_at: inspection.scheduled_at ? inspection.scheduled_at.slice(0, 16) : "", location: inspection.location || "" });
    setModal("schedule");
  }

  function submitDamage() {
    setError("");
    if (!damageForm.zone) {
      setError("Select a damage zone.");
      return;
    }
    addDamage.mutate();
  }

  function submitComplete(event) {
    event?.preventDefault();
    setError("");
    if (!completeForm.report_summary.trim()) {
      setError("Enter an inspection report summary.");
      return;
    }
    const body = new FormData();
    body.append("report_summary", completeForm.report_summary);
    body.append("overall_condition", completeForm.overall_condition);
    if (completeForm.report_file) body.append("report_file", completeForm.report_file);
    action.mutate({ key: "complete", formData: body });
  }

  function submitSchedule(event) {
    event?.preventDefault();
    setError("");
    if (!scheduleForm.inspector || !scheduleForm.scheduled_at || !scheduleForm.location.trim()) {
      setError("Choose an inspector and enter the schedule and location.");
      return;
    }
    const scheduledAt = new Date(scheduleForm.scheduled_at);
    if (Number.isNaN(scheduledAt.getTime())) {
      setError("Enter a valid inspection date and time.");
      return;
    }
    action.mutate({
      key: "schedule",
      json: {
        inspector: scheduleForm.inspector,
        scheduled_at: scheduledAt.toISOString(),
        location: scheduleForm.location.trim(),
      },
    });
  }

  const damageTree = inspection.damages || [];

  return (
    <div>
      <Link to={user?.role === "inspector" ? "/inspector/inspections" : "/inspections"} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to inspections</Link>
      <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">{inspection.inspection_number}</p>
            <StatusBadge status={inspection.status} />
          </div>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{inspection.vehicle_summary?.registration_number}</h1>
          <p className="mt-2 text-sm text-ink-500">{titleize(inspection.inspection_type)} · {inspection.vehicle_summary?.make} {inspection.vehicle_summary?.model} {inspection.vehicle_summary?.year}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {inspection.status === "scheduled" && (isAdmin || user?.id === inspection.inspector) && <Button icon={Play} onClick={() => action.mutate({ key: "start", json: {} })} loading={action.isPending}>Start inspection</Button>}
          {canComplete && <Button icon={CheckCircle2} variant="lime" onClick={() => { setError(""); setCompleteForm({ report_summary: inspection.report_summary || "", overall_condition: inspection.overall_condition || "good", report_file: null }); setModal("complete"); }}>Complete</Button>}
          {canSchedule && <Button variant="secondary" onClick={openSchedule}>Schedule</Button>}
          {canEdit && <Button variant="secondary" icon={Camera} onClick={() => { setError(""); setAiResult(null); setAiFile(null); setModal("ai"); }}>AI assist</Button>}
          {canEdit && <Button variant="brand" icon={Plus} onClick={() => openDamage("")}>Record damage</Button>}
        </div>
      </div>

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <div>
          <Suspense fallback={<div className="surface p-8 text-center text-sm text-ink-500">Loading 3D inspection…</div>}>
            <VehicleScene damages={damageTree} onZone={canEdit ? openDamage : undefined} selectedZone={selectedZone} interactive={canEdit} />
          </Suspense>
          {canEdit && <p className="mt-2 text-center text-xs text-ink-400">Rotate the vehicle and tap a marker to record damage. You can also use the zone list.</p>}

          <div className="mt-7">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-ink-950">Recorded damage</h2>
              <span className="text-xs text-ink-400">{damageTree.length} record{damageTree.length === 1 ? "" : "s"}</span>
            </div>
            <div className="surface divide-y divide-ink-100">
              {damageTree.length ? damageTree.map((damage) => (
                <div key={damage.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <div className="flex items-center gap-3">
                    <span className={`grid h-9 w-9 place-items-center rounded-xl ${damage.severity === "severe" ? "bg-red-50 text-red-600" : damage.severity === "moderate" ? "bg-amber-50 text-amber-600" : "bg-yellow-50 text-yellow-600"}`}><Wrench className="h-4 w-4" /></span>
                    <div>
                      <p className="text-xs font-bold text-ink-900">{INSPECTION_ZONES.find((zone) => zone.key === damage.zone)?.label || titleize(damage.zone)}</p>
                      <p className="mt-0.5 text-[10px] capitalize text-ink-400">{damage.severity} · {formatDate(damage.created_at)}</p>
                      {damage.description && <p className="mt-1 text-[11px] text-ink-500">{damage.description}</p>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="text-xs font-bold text-ink-800">{damage.estimated_repair_cost ? `KES ${Number(damage.estimated_repair_cost).toLocaleString()}` : "—"}</p>
                    {damage.photo_download_url && (
                      <FileDownload
                        url={damage.photo_download_url}
                        filename={damage.photo_filename}
                        className="text-xs font-semibold text-brand-700 hover:underline"
                      >
                        Photo
                      </FileDownload>
                    )}
                    {canEdit && <button onClick={() => deleteDamage.mutate(damage.id)} className="rounded-lg p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600" aria-label="Delete damage"><Trash2 className="h-3.5 w-3.5" /></button>}
                  </div>
                </div>
              )) : <p className="p-5 text-sm text-ink-500">No damage recorded. Tap a marker on the vehicle to start.</p>}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface p-5">
            <h2 className="font-display text-base font-bold text-ink-950">Inspection details</h2>
            <div className="mt-4 space-y-4">
              <DetailItem label="Type">{titleize(inspection.inspection_type)}</DetailItem>
              <DetailItem label="Inspector">{inspection.inspector_name || "Unassigned"}</DetailItem>
              <DetailItem label="Requested by">{inspection.requested_by_name}</DetailItem>
              <DetailItem label="Organization">{inspection.organization_name || "—"}</DetailItem>
              <DetailItem label="Scheduled">{inspection.scheduled_at ? formatDateTime(inspection.scheduled_at) : "Not scheduled"}</DetailItem>
              <DetailItem label="Location"><span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-ink-400" />{inspection.location || "—"}</span></DetailItem>
              <DetailItem label="Completed">{inspection.completed_at ? formatDateTime(inspection.completed_at) : "—"}</DetailItem>
            </div>
            {inspection.notes && <div className="mt-4 rounded-xl bg-ink-50 p-3 text-xs leading-relaxed text-ink-600">{inspection.notes}</div>}
          </div>

          {inspection.report_summary && (
            <div className="surface p-5">
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-600" /><h2 className="font-display text-base font-bold text-ink-950">Inspection report</h2></div>
              <p className="mt-3 text-xs leading-relaxed text-ink-600">{inspection.report_summary}</p>
              <div className="mt-3 flex items-center justify-between">
                <StatusBadge status={inspection.overall_condition || "completed"} />
                {inspection.report_download_url && (
                  <FileDownload
                    url={inspection.report_download_url}
                    filename={inspection.report_filename}
                    className="text-xs font-semibold text-brand-700 hover:underline"
                  >
                    Download report
                  </FileDownload>
                )}
              </div>
            </div>
          )}

          {inspection.status === "requested" && !canSchedule && <Alert tone="info">Waiting for the provider to assign an inspector and schedule the visit.</Alert>}
        </div>
      </div>

      <Modal
        open={modal === "damage"}
        onClose={() => { setModal(null); setSelectedZone(""); }}
        title="Record damage"
        description="Describe the damage and attach a photo if available."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitDamage} loading={addDamage.isPending}>Save damage</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Zone" required value={damageForm.zone} onChange={(event) => setDamageForm((current) => ({ ...current, zone: event.target.value }))} options={INSPECTION_ZONES.map((zone) => ({ value: zone.key, label: zone.label }))} placeholder="Select zone" />
          <Select label="Severity" value={damageForm.severity} onChange={(event) => setDamageForm((current) => ({ ...current, severity: event.target.value }))} options={SEVERITIES} />
          <Input label="Estimated repair cost (KES)" type="number" min="0" value={damageForm.estimated_repair_cost} onChange={(event) => setDamageForm((current) => ({ ...current, estimated_repair_cost: event.target.value }))} />
          <Textarea label="Description" value={damageForm.description} onChange={(event) => setDamageForm((current) => ({ ...current, description: event.target.value }))} placeholder="What damage can you see?" />
          <Input label="Photo" type="file" accept="image/*" onChange={(event) => setDamageForm((current) => ({ ...current, photo: event.target.files?.[0] || null }))} />
        </div>
      </Modal>

      <Modal
        open={modal === "schedule"}
        onClose={() => setModal(null)}
        title="Schedule inspection"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitSchedule} loading={action.isPending}>Schedule</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Inspector" required placeholder="Select inspector" value={scheduleForm.inspector} onChange={(event) => setScheduleForm((current) => ({ ...current, inspector: event.target.value }))} options={inspectorOptions} />
          <Input label="Scheduled at" type="datetime-local" required value={scheduleForm.scheduled_at} onChange={(event) => setScheduleForm((current) => ({ ...current, scheduled_at: event.target.value }))} />
          <Input label="Location" required value={scheduleForm.location} onChange={(event) => setScheduleForm((current) => ({ ...current, location: event.target.value }))} />
          {!inspectorOptions.length && <Alert tone="warning">No inspectors found in your organization. Add an inspector member first.</Alert>}
        </div>
      </Modal>

      <Modal
        open={modal === "complete"}
        onClose={() => setModal(null)}
        title="Complete inspection"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitComplete} loading={action.isPending} icon={CheckCircle2}>Complete inspection</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Textarea label="Report summary" required value={completeForm.report_summary} onChange={(event) => setCompleteForm((current) => ({ ...current, report_summary: event.target.value }))} placeholder="Condition, damage findings and recommendation" />
          <Select label="Overall condition" value={completeForm.overall_condition} onChange={(event) => setCompleteForm((current) => ({ ...current, overall_condition: event.target.value }))} options={CONDITIONS} />
          <Input label="Report file" type="file" onChange={(event) => setCompleteForm((current) => ({ ...current, report_file: event.target.files?.[0] || null }))} />
        </div>
      </Modal>

      <Modal
        open={modal === "ai"}
        onClose={() => setModal(null)}
        title="AI damage assist"
        description="Advisory only. An inspector must verify every result."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Close</Button><Button onClick={() => aiAssist.mutate()} loading={aiAssist.isPending} disabled={!aiFile} icon={Bot}>Analyse image</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Damage photo" type="file" accept="image/*" onChange={(event) => setAiFile(event.target.files?.[0] || null)} />
          {aiResult && (
            <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sky-900">
              <div className="flex items-center gap-2"><Bot className="h-4 w-4" /><p className="text-sm font-bold">Suggested severity: {aiResult.suggested_severity}</p></div>
              <p className="mt-2 text-xs leading-relaxed">{aiResult.explanation}</p>
              <p className="mt-2 text-[10px] font-semibold">Confidence {Math.round((aiResult.confidence || 0) * 100)}% · {aiResult.requires_human_review ? "Human review required" : ""}</p>
            </div>
          )}
          <Alert tone="warning">This tool does not change claim or inspection decisions automatically.</Alert>
        </div>
      </Modal>
    </div>
  );
}
