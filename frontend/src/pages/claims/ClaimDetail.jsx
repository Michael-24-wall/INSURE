import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock3, FileText, Gavel, Upload, UserRound } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, formatDate, formatDateTime, localDateTimeISO } from "../../lib/format";
import { Alert, Button, Input, Modal, PageLoader, Select, StatusBadge, Textarea } from "../../components/ui";
import { DetailItem } from "../../components/DataTable";
import FileDownload from "../../components/FileDownload";

const DOC_TYPES = [
  { value: "police_report", label: "Police report" },
  { value: "photo", label: "Photograph" },
  { value: "estimate", label: "Repair estimate" },
  { value: "invoice", label: "Invoice" },
  { value: "id", label: "Identification" },
  { value: "medical", label: "Medical report" },
  { value: "other", label: "Other" },
];

export default function ClaimDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [approvedAmount, setApprovedAmount] = useState("");
  const [settleForm, setSettleForm] = useState({ settled_amount: "", settlement_reference: "" });
  const [inspectionForm, setInspectionForm] = useState({ inspector: "", scheduled_at: localDateTimeISO(24), location: "" });
  const [docType, setDocType] = useState("photo");
  const [docFile, setDocFile] = useState(null);
  const [docNotes, setDocNotes] = useState("");

  const claimQuery = useQuery({
    queryKey: ["claim", id],
    queryFn: async () => (await api.get(`/claims/${id}/`)).data,
  });
  const isCustomer = user?.role === "customer";
  const isProvider = ["provider_admin", "provider_staff", "claims_officer", "admin", "super_admin"].includes(user?.role);
  const orgId = user?.memberships?.[0]?.organization_id;

  const members = useQuery({
    queryKey: ["organization-members", orgId],
    queryFn: async () => (await api.get(`/organizations/${orgId}/members/`)).data,
    enabled: Boolean(orgId) && isProvider,
  });

  const memberRows = listData(members.data);
  const inspectors = memberRows.filter((member) => member.user_role === "inspector" || member.role === "inspector");
  const officers = memberRows.filter((member) => ["claims_officer", "provider_admin"].includes(member.user_role));

  const claim = claimQuery.data;
  const actions = useMemo(() => {
    if (!claim || isCustomer) return [];
    const map = {
      submitted: [["review", "Start review"], ["reject", "Reject"]],
      under_review: [["request-info", "Request information"], ["schedule-inspection", "Schedule inspection"], ["approve", "Approve"], ["reject", "Reject"]],
      info_required: [["review", "Resume review"], ["reject", "Reject"]],
      inspection_scheduled: [["assess", "Start assessment"], ["reject", "Reject"]],
      assessment: [["approve", "Approve"], ["reject", "Reject"]],
      approved: [["settle", "Record settlement"], ["close", "Close claim"]],
      settled: [["close", "Close claim"]],
    };
    return map[claim.status] || [];
  }, [claim, isCustomer]);

  const mutate = useMutation({
    mutationFn: async ({ key, body }) => (await api.post(`/claims/${id}/${key}/`, body)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claim", id] });
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      toast.push("Claim updated.", "success");
      setModal(null);
      setNotes("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const upload = useMutation({
    mutationFn: async () => {
      const body = new FormData();
      body.append("document_type", docType);
      body.append("file", docFile);
      body.append("notes", docNotes);
      return (await api.post(`/claims/${id}/documents/`, body)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claim", id] });
      toast.push("Document uploaded.", "success");
      setModal(null);
      setDocFile(null);
      setDocNotes("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const assign = useMutation({
    mutationFn: async (officer) => (await api.post(`/claims/${id}/assign-officer/`, { officer })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claim", id] });
      toast.push("Claims officer assigned.", "success");
      setModal(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (claimQuery.isLoading) return <PageLoader />;
  if (claimQuery.isError) return <Alert>Could not load this claim.</Alert>;

  function open(key) {
    setError("");
    setNotes("");
    setModal(key);
    if (key === "approve") setApprovedAmount(claim.approved_amount || claim.amount_claimed);
    if (key === "settle") setSettleForm({ settled_amount: claim.approved_amount || claim.amount_claimed, settlement_reference: "" });
    if (key === "schedule-inspection") setInspectionForm({ inspector: "", scheduled_at: localDateTimeISO(24), location: claim.location });
  }

  function submitAction(event) {
    event?.preventDefault();
    setError("");
    const keyMap = { "request-info": "request-info", "schedule-inspection": "schedule-inspection" };
    const path = keyMap[modal] || modal;
    let body = { notes };
    if (modal === "approve") body = { approved_amount: Number(approvedAmount), notes };
    if (modal === "reject") body = { notes };
    if (modal === "settle") {
      if (!settleForm.settlement_reference.trim()) { setError("Enter the settlement reference."); return; }
      body = { settled_amount: Number(settleForm.settled_amount), settlement_reference: settleForm.settlement_reference.trim() };
    }
    if (modal === "schedule-inspection") {
      if (!inspectionForm.inspector || !inspectionForm.scheduled_at || !inspectionForm.location.trim()) {
        setError("Choose an inspector and enter the schedule and location.");
        return;
      }
      const scheduledAt = new Date(inspectionForm.scheduled_at);
      if (Number.isNaN(scheduledAt.getTime())) { setError("Enter a valid inspection date and time."); return; }
      body = { ...inspectionForm, location: inspectionForm.location.trim(), scheduled_at: scheduledAt.toISOString() };
    }
    mutate.mutate({ key: path, body });
  }

  function submitWithdraw() {
    mutate.mutate({ key: "withdraw", body: { notes } });
  }

  return (
    <div>
      <Link to={isCustomer ? "/app/claims" : "/claims"} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to claims</Link>
      <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">{claim.claim_number}</p>
            <StatusBadge status={claim.status} />
          </div>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{claim.claim_type?.replace(/_/g, " ")} claim</h1>
          <p className="mt-2 text-sm text-ink-500">{claim.vehicle_summary?.registration_number} · {claim.policy_number} · {claim.insurer_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {actions.map(([key, label]) => (
            <Button key={key} variant={key === "reject" ? "danger-soft" : key === "approve" ? "lime" : key === "review" ? "brand" : "secondary"} onClick={() => open(key)}>{label}</Button>
          ))}
          {isCustomer && claim.status === "info_required" && <Button variant="brand" onClick={() => open("respond")}>Respond</Button>}
          {isCustomer && ["draft", "submitted", "under_review", "info_required"].includes(claim.status) && <Button variant="danger-soft" onClick={() => open("withdraw")}>Withdraw claim</Button>}
        </div>
      </div>

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-6">
          <div className="surface p-6">
            <h2 className="font-display text-lg font-bold text-ink-950">Incident details</h2>
            <div className="mt-5 grid gap-5 sm:grid-cols-3">
              <DetailItem label="Incident date">{formatDate(claim.incident_date)}</DetailItem>
              <DetailItem label="Incident time">{claim.incident_time || "—"}</DetailItem>
              <DetailItem label="Amount claimed">{formatCurrency(claim.amount_claimed)}</DetailItem>
              <DetailItem label="Location">{claim.location}</DetailItem>
              <DetailItem label="Police report">{claim.police_report_number || "—"}</DetailItem>
              <DetailItem label="Claims officer">{claim.officer_name || "Unassigned"}</DetailItem>
              <DetailItem label="Approved amount">{claim.approved_amount ? formatCurrency(claim.approved_amount) : "—"}</DetailItem>
              <DetailItem label="Settled amount">{claim.settled_amount ? formatCurrency(claim.settled_amount) : "—"}</DetailItem>
              <DetailItem label="Settlement ref">{claim.settlement_reference || "—"}</DetailItem>
            </div>
            <p className="mt-5 rounded-xl bg-ink-50 p-4 text-sm leading-relaxed text-ink-600">{claim.description}</p>
            {claim.decision_notes && <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900"><strong>Decision notes:</strong> {claim.decision_notes}</div>}
          </div>

          <div>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-ink-950">Evidence & documents</h2>
              <Button size="sm" variant="secondary" icon={Upload} onClick={() => { setError(""); setModal("upload"); }}>Upload</Button>
            </div>
            <div className="surface divide-y divide-ink-100">
              {claim.documents?.length ? claim.documents.map((doc) => (
                <div key={doc.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink-100 text-ink-500"><FileText className="h-4 w-4" /></span>
                    <div>
                      <p className="text-xs font-bold text-ink-900">{doc.document_type?.replace(/_/g, " ")}</p>
                      <p className="text-[10px] text-ink-400">{formatDate(doc.created_at)} · {doc.uploaded_by_name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {doc.ai_classification && <span className="text-[10px] text-ink-400">AI: {doc.ai_classification}</span>}
                    <FileDownload
                      url={doc.download_url}
                      filename={doc.filename}
                      className="text-xs font-semibold text-brand-700 hover:underline"
                    >
                      Open
                    </FileDownload>
                  </div>
                </div>
              )) : <p className="p-5 text-sm text-ink-500">No documents uploaded.</p>}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6 text-white">
            <Gavel className="h-7 w-7 text-lime-300" />
            <p className="mt-4 font-display text-2xl font-bold tracking-tight">{formatCurrency(claim.approved_amount || claim.amount_claimed)}</p>
            <p className="mt-1 text-xs text-white/50">{claim.approved_amount ? "Approved amount" : "Amount claimed"}</p>
            <p className="mt-4 text-xs leading-relaxed text-white/55">Claims are assessed against the policy terms. Keep all evidence and correspondence available.</p>
          </div>

          <div className="surface p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-base font-bold text-ink-950">Claim timeline</h2>
              {isProvider && claim.status === "submitted" && officers.length > 0 && (
                <Button size="sm" variant="ghost" icon={UserRound} onClick={() => setModal("assign")}>Assign</Button>
              )}
            </div>
            <div className="mt-4 space-y-4">
              {claim.status_history?.length ? claim.status_history.map((entry, index) => (
                <div key={entry.id} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span className={`grid h-6 w-6 place-items-center rounded-full ${index === 0 ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-400"}`}><CheckCircle2 className="h-3.5 w-3.5" /></span>
                    {index < claim.status_history.length - 1 && <span className="h-8 w-px bg-ink-100" />}
                  </div>
                  <div className="pb-1">
                    <p className="text-xs font-bold text-ink-800">{entry.to_status?.replace(/_/g, " ")}</p>
                    <p className="mt-0.5 flex items-center gap-1 text-[10px] text-ink-400"><Clock3 className="h-3 w-3" /> {formatDateTime(entry.created_at)} · {entry.changed_by_name || "System"}</p>
                    {entry.notes && <p className="mt-1 text-[11px] leading-relaxed text-ink-500">{entry.notes}</p>}
                  </div>
                </div>
              )) : <p className="text-sm text-ink-500">No status updates yet.</p>}
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={modal === "upload"}
        onClose={() => setModal(null)}
        title="Upload claim document"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={() => upload.mutate()} loading={upload.isPending} disabled={!docFile}>Upload</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Document type" value={docType} onChange={(event) => setDocType(event.target.value)} options={DOC_TYPES} />
          <Input label="File" type="file" required onChange={(event) => setDocFile(event.target.files?.[0] || null)} />
          <Input label="Notes" value={docNotes} onChange={(event) => setDocNotes(event.target.value)} placeholder="Optional" />
        </div>
      </Modal>

      <Modal
        open={modal === "assign"}
        onClose={() => setModal(null)}
        title="Assign claims officer"
        description="The assigned officer will be notified."
      >
        <div className="space-y-3">
          {error && <Alert>{error}</Alert>}
          {officers.map((officer) => (
            <div key={officer.id} className="flex items-center justify-between gap-3 rounded-xl border border-ink-100 p-3">
              <div>
                <p className="text-xs font-bold text-ink-900">{officer.user_name}</p>
                <p className="text-[10px] text-ink-400">{officer.user_email}</p>
              </div>
              <Button size="sm" variant="secondary" onClick={() => assign.mutate(officer.user)} loading={assign.isPending}>Assign</Button>
            </div>
          ))}
          {!officers.length && <Alert tone="info">No claims officers found in your organization.</Alert>}
        </div>
      </Modal>

      <Modal
        open={Boolean(modal && !["upload", "assign"].includes(modal))}
        onClose={() => setModal(null)}
        title={{
          review: "Start claim review",
          "request-info": "Request more information",
          approve: "Approve claim",
          reject: "Reject claim",
          settle: "Record settlement",
          close: "Close claim",
          withdraw: "Withdraw claim",
          respond: "Respond to insurer",
        }[modal] || "Update claim"}
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button variant={modal === "reject" ? "danger" : "brand"} onClick={modal === "withdraw" ? submitWithdraw : submitAction} loading={mutate.isPending}>Confirm</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          {modal === "approve" && <Input label="Approved amount (KES)" type="number" min="0" value={approvedAmount} onChange={(event) => setApprovedAmount(event.target.value)} />}
          {modal === "settle" && (
            <>
              <Input label="Settled amount (KES)" type="number" min="0" value={settleForm.settled_amount} onChange={(event) => setSettleForm((current) => ({ ...current, settled_amount: event.target.value }))} />
              <Input label="Settlement reference" required value={settleForm.settlement_reference} onChange={(event) => setSettleForm((current) => ({ ...current, settlement_reference: event.target.value }))} />
            </>
          )}
          {modal === "schedule-inspection" && (
            <>
              <Select label="Inspector" required placeholder="Select inspector" value={inspectionForm.inspector} onChange={(event) => setInspectionForm((current) => ({ ...current, inspector: event.target.value }))} options={inspectors.map((inspector) => ({ value: inspector.user, label: inspector.user_name }))} />
              <Input label="Scheduled at" type="datetime-local" required value={inspectionForm.scheduled_at} onChange={(event) => setInspectionForm((current) => ({ ...current, scheduled_at: event.target.value }))} />
              <Input label="Location" required value={inspectionForm.location} onChange={(event) => setInspectionForm((current) => ({ ...current, location: event.target.value }))} />
            </>
          )}
          <Textarea label={modal === "reject" || modal === "request-info" ? "Details" : "Notes"} required={["reject", "request-info"].includes(modal)} value={notes} onChange={(event) => setNotes(event.target.value)} />
        </div>
      </Modal>
    </div>
  );
}
