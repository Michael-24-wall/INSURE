import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileText, Plus, Save, ShieldCheck, UserPlus, Users, X } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { formatDate, titleize } from "../../lib/format";
import { Alert, Badge, Button, Input, Modal, PageLoader, PageHeader, Select, StatusBadge, Textarea } from "../../components/ui";
import FileDownload from "../../components/FileDownload";

const MEMBER_ROLES = [
  { value: "admin", label: "Administrator" },
  { value: "staff", label: "Staff" },
  { value: "agent", label: "Agent" },
  { value: "inspector", label: "Inspector" },
  { value: "claims", label: "Claims officer" },
];

const DOCUMENT_TYPES = [
  "Certificate of incorporation",
  "IRA license",
  "Tax compliance certificate",
  "Financial statement",
  "Other",
];

export default function ProviderSettings() {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const orgId = user?.memberships?.[0]?.organization_id;
  const membership = user?.memberships?.[0];
  const canManage = ["provider_admin", "admin", "super_admin"].includes(user?.role);
  const [form, setForm] = useState(null);
  const [modal, setModal] = useState(null);
  const [memberForm, setMemberForm] = useState({ email: "", role: "staff" });
  const [docForm, setDocForm] = useState({ document_type: DOCUMENT_TYPES[0], file: null });
  const [error, setError] = useState("");

  const org = useQuery({
    queryKey: ["organization", orgId],
    queryFn: async () => (await api.get(`/organizations/${orgId}/`)).data,
    enabled: Boolean(orgId),
  });
  const members = useQuery({
    queryKey: ["organization-members", orgId],
    queryFn: async () => (await api.get(`/organizations/${orgId}/members/`)).data,
    enabled: Boolean(orgId),
  });
  const documents = useQuery({
    queryKey: ["organization-documents", orgId],
    queryFn: async () => (await api.get(`/organizations/${orgId}/documents/`)).data,
    enabled: Boolean(orgId),
  });

  useEffect(() => {
    if (org.data && !form) {
      setForm({
        name: org.data.name,
        registration_number: org.data.registration_number || "",
        email: org.data.email || "",
        phone: org.data.phone || "",
        website: org.data.website || "",
        address: org.data.address || "",
        description: org.data.description || "",
      });
    }
  }, [org.data, form]);

  const saveOrg = useMutation({
    mutationFn: async () => (await api.patch(`/organizations/${orgId}/`, form)).data,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["organization", orgId] });
      setUser((current) => current ? {
        ...current,
        memberships: current.memberships.map((item) => String(item.organization_id) === String(orgId) ? { ...item, organization_name: data.name } : item),
      } : current);
      toast.push("Organization details saved.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const addMember = useMutation({
    mutationFn: async () => (await api.post(`/organizations/${orgId}/members/`, memberForm)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
      toast.push("Member added.", "success");
      setModal(null);
      setMemberForm({ email: "", role: "staff" });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const updateMember = useMutation({
    mutationFn: async ({ member, values }) => (await api.patch(`/organizations/${orgId}/members/${member.id}/`, values)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
      toast.push("Member updated.", "success");
    },
    onError: (err) => toast.push(getErrorMessage(err), "error"),
  });

  const removeMember = useMutation({
    mutationFn: async (member) => api.delete(`/organizations/${orgId}/members/${member.id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-members", orgId] });
      toast.push("Member deactivated.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const uploadDocument = useMutation({
    mutationFn: async () => {
      const body = new FormData();
      body.append("document_type", docForm.document_type);
      body.append("file", docForm.file);
      return (await api.post(`/organizations/${orgId}/documents/`, body)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-documents", orgId] });
      toast.push("Document uploaded.", "success");
      setModal(null);
      setDocForm({ document_type: DOCUMENT_TYPES[0], file: null });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (!orgId) return <Alert>No provider organization is linked to your account.</Alert>;
  if (org.isLoading || !form) return <PageLoader />;
  if (org.isError) return <Alert>Could not load your organization.</Alert>;

  function submitOrg(event) {
    event.preventDefault();
    setError("");
    saveOrg.mutate();
  }

  function submitMember(event) {
    event.preventDefault();
    setError("");
    addMember.mutate();
  }

  function submitDocument(event) {
    event.preventDefault();
    setError("");
    if (!docForm.file) {
      setError("Choose a document to upload.");
      return;
    }
    uploadDocument.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Organization"
        title="Company settings"
        description="Keep your provider profile, team and compliance documents up to date."
        actions={<Badge tone={org.data.status === "verified" ? "green" : org.data.status === "pending" ? "amber" : "red"}>{titleize(org.data.status)}</Badge>}
      />

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}
      {org.data.status === "pending" && <div className="mb-6"><Alert tone="warning" title="Verification pending">Your organization is under review. Products and quotes may be limited until verification is complete.</Alert></div>}
      {org.data.status === "rejected" && <div className="mb-6"><Alert title="Verification rejected">{org.data.rejection_reason || "Contact platform support for details."}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <form onSubmit={submitOrg} className="surface p-5 sm:p-6">
            <div className="flex items-center gap-2"><Building2 className="h-4 w-4 text-brand-700" /><h2 className="font-display text-lg font-bold text-ink-950">Company profile</h2></div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Input label="Company name" required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} disabled={!canManage} />
              <Input label="Registration number" value={form.registration_number} onChange={(event) => setForm((current) => ({ ...current, registration_number: event.target.value }))} disabled={!canManage} />
              <Input label="Email" type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} disabled={!canManage} />
              <Input label="Phone" value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} disabled={!canManage} />
              <Input label="Website" value={form.website} onChange={(event) => setForm((current) => ({ ...current, website: event.target.value }))} disabled={!canManage} />
              <Input label="Address" value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} disabled={!canManage} />
            </div>
            <Textarea className="mt-4" label="About the company" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} disabled={!canManage} />
            {canManage && <div className="mt-5 flex justify-end"><Button type="submit" icon={Save} loading={saveOrg.isPending}>Save changes</Button></div>}
          </form>

          <div className="surface p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2"><Users className="h-4 w-4 text-brand-700" /><h2 className="font-display text-lg font-bold text-ink-950">Team members</h2></div>
              {canManage && <Button size="sm" variant="secondary" icon={UserPlus} onClick={() => { setError(""); setModal("member"); }}>Add member</Button>}
            </div>
            <div className="mt-4 divide-y divide-ink-100">
              {listData(members.data).map((member) => (
                <div key={member.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="text-sm font-semibold text-ink-900">{member.user_name || member.user_email}</p>
                    <p className="mt-0.5 text-xs text-ink-400">{member.user_email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="brand">{titleize(member.role)}</Badge>
                    {member.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}
                    {canManage && member.role !== "owner" && (
                      <>
                        <Select value={member.role} onChange={(event) => updateMember.mutate({ member, values: { role: event.target.value } })} options={MEMBER_ROLES} className="w-36" />
                        {member.is_active && <button onClick={() => removeMember.mutate(member)} className="rounded-lg p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600" aria-label="Deactivate member"><X className="h-4 w-4" /></button>}
                      </>
                    )}
                  </div>
                </div>
              ))}
              {!listData(members.data).length && <p className="py-4 text-sm text-ink-400">No members found.</p>}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="surface p-5">
            <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-600" /><h2 className="font-display text-base font-bold text-ink-950">Verification</h2></div>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between"><span className="text-ink-500">Status</span><StatusBadge status={org.data.status} /></div>
              <div className="flex items-center justify-between"><span className="text-ink-500">Type</span><span className="font-semibold text-ink-800">{titleize(org.data.organization_type)}</span></div>
              <div className="flex items-center justify-between"><span className="text-ink-500">Members</span><span className="font-semibold text-ink-800">{org.data.member_count}</span></div>
              <div className="flex items-center justify-between"><span className="text-ink-500">Verified</span><span className="font-semibold text-ink-800">{org.data.verified_at ? formatDate(org.data.verified_at) : "—"}</span></div>
            </div>
            <div className="mt-4 rounded-xl bg-ink-50 p-3 text-xs leading-relaxed text-ink-500">Your membership role is <strong>{titleize(membership?.role || "")}</strong>. Organization verification is managed by platform administrators.</div>
          </div>

          <div className="surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2"><FileText className="h-4 w-4 text-brand-700" /><h2 className="font-display text-base font-bold text-ink-950">Compliance documents</h2></div>
              <Button size="sm" variant="secondary" icon={Plus} onClick={() => { setError(""); setModal("document"); }}>Upload</Button>
            </div>
            <div className="mt-4 divide-y divide-ink-100">
              {(documents.data || []).map((document) => (
                <div key={document.id} className="flex items-center justify-between gap-3 py-3">
                  <div>
                    <p className="text-xs font-semibold text-ink-900">{document.document_type}</p>
                    <p className="mt-0.5 text-[10px] text-ink-400">{formatDate(document.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {document.is_verified ? <Badge tone="green">Verified</Badge> : <Badge tone="amber">Review</Badge>}
                    <FileDownload
                      url={document.download_url}
                      filename={document.filename}
                      className="text-xs font-bold text-brand-700 hover:underline"
                    >
                      View
                    </FileDownload>
                  </div>
                </div>
              ))}
              {!(documents.data || []).length && <p className="py-4 text-xs text-ink-400">No documents uploaded yet.</p>}
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={modal === "member"}
        onClose={() => setModal(null)}
        title="Add team member"
        description="The person must already have an account."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitMember} loading={addMember.isPending} icon={UserPlus}>Add member</Button></>}
      >
        <form onSubmit={submitMember} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Email address" type="email" required value={memberForm.email} onChange={(event) => setMemberForm((current) => ({ ...current, email: event.target.value }))} />
          <Select label="Role" value={memberForm.role} onChange={(event) => setMemberForm((current) => ({ ...current, role: event.target.value }))} options={MEMBER_ROLES} />
        </form>
      </Modal>

      <Modal
        open={modal === "document"}
        onClose={() => setModal(null)}
        title="Upload compliance document"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitDocument} loading={uploadDocument.isPending}>Upload</Button></>}
      >
        <form onSubmit={submitDocument} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Document type" value={docForm.document_type} onChange={(event) => setDocForm((current) => ({ ...current, document_type: event.target.value }))} options={DOCUMENT_TYPES.map((type) => ({ value: type, label: type }))} />
          <Input label="File" type="file" required onChange={(event) => setDocForm((current) => ({ ...current, file: event.target.files?.[0] || null }))} />
        </form>
      </Modal>
    </div>
  );
}
