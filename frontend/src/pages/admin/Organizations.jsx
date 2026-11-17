import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle2, Plus, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import api, { getErrorMessage, listData, pageCount } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { formatDate, titleize } from "../../lib/format";
import { Alert, Button, Input, Modal, PageHeader, Pagination, SearchInput, Select, Stat, StatusBadge, Tabs, Textarea } from "../../components/ui";
import { DataTable } from "../../components/DataTable";

const ORG_TYPES = [
  { value: "insurer", label: "Insurance provider" },
  { value: "agency", label: "Insurance agency" },
  { value: "inspection", label: "Inspection company" },
  { value: "platform", label: "Platform" },
];

const emptyOrg = { name: "", organization_type: "insurer", registration_number: "", email: "", phone: "", website: "", address: "", description: "" };

export default function AdminOrganizations() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [verifyAction, setVerifyAction] = useState(null);
  const [reason, setReason] = useState("");
  const [modal, setModal] = useState(null);
  const [orgForm, setOrgForm] = useState(emptyOrg);
  const [error, setError] = useState("");

  const orgs = useQuery({
    queryKey: ["admin-organizations", { status, search, page }],
    queryFn: async () => (await api.get(`/organizations/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["admin-organizations", "counts"],
    queryFn: async () => {
      const values = ["pending", "verified", "suspended", "rejected"];
      const results = await Promise.all(values.map(async (value) => {
        const { data } = await api.get(`/organizations/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const verify = useMutation({
    mutationFn: async ({ action, reasonText }) => (await api.post(`/organizations/${selected.id}/verify/`, { action, reason: reasonText || "" })).data,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-organizations"] });
      toast.push(`Organization ${data.status}.`, "success");
      setModal(null);
      setSelected(null);
      setReason("");
      setVerifyAction(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const create = useMutation({
    mutationFn: async () => (await api.post("/organizations/", orgForm)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-organizations"] });
      toast.push("Organization created. Verify it to activate products.", "success");
      setModal(null);
      setOrgForm(emptyOrg);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const rows = listData(orgs.data);
  const total = pageCount(orgs.data);

  function openAction(row, action) {
    setError("");
    setSelected(row);
    setVerifyAction(action);
    setReason("");
    setModal("verify");
  }

  function submitVerify(event) {
    event.preventDefault();
    setError("");
    if (verifyAction === "reject" && !reason.trim()) {
      setError("Provide a reason for the rejection.");
      return;
    }
    verify.mutate({ action: verifyAction, reasonText: reason });
  }

  function submitCreate(event) {
    event.preventDefault();
    setError("");
    create.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Platform administration"
        title="Organizations"
        description="Verify insurers, agencies and inspection companies before they trade on the marketplace."
        actions={<Button icon={Plus} onClick={() => { setError(""); setOrgForm(emptyOrg); setModal("create"); }}>New organization</Button>}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={ShieldAlert} label="Pending review" value={counts.data?.pending ?? "—"} tone="amber" />
        <Stat icon={ShieldCheck} label="Verified" value={counts.data?.verified ?? "—"} tone="lime" />
        <Stat icon={ShieldX} label="Suspended / rejected" value={(counts.data?.suspended || 0) + (counts.data?.rejected || 0)} tone="red" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "pending", label: "Pending", count: counts.data?.pending },
          { value: "verified", label: "Verified", count: counts.data?.verified },
          { value: "suspended", label: "Suspended", count: counts.data?.suspended },
          { value: "rejected", label: "Rejected", count: counts.data?.rejected },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search organizations" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={orgs.isLoading}
        error={orgs.isError}
        onRetry={orgs.refetch}
        rows={rows}
        columns={[
          {
            header: "Organization",
            cell: (row) => (
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-700"><Building2 className="h-4 w-4" /></span>
                <div>
                  <p className="text-xs font-bold text-ink-900">{row.name}</p>
                  <p className="mt-0.5 text-[10px] text-ink-400">{titleize(row.organization_type)} · {row.registration_number || "No reg. number"}</p>
                </div>
              </div>
            ),
          },
          { header: "Contact", cell: (row) => <div><p className="text-xs text-ink-600">{row.email || "—"}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.phone || ""}</p></div> },
          { header: "Members", cell: (row) => <span className="text-xs font-semibold text-ink-700">{row.member_count}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "Created", cell: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span> },
          {
            header: "",
            className: "text-right",
            cell: (row) => (
              <div className="flex justify-end gap-1">
                {row.status === "pending" && <><Button size="sm" variant="ghost" onClick={() => openAction(row, "verify")}>Verify</Button><Button size="sm" variant="ghost" onClick={() => openAction(row, "reject")}>Reject</Button></>}
                {row.status === "verified" && <Button size="sm" variant="ghost" onClick={() => openAction(row, "suspend")}>Suspend</Button>}
                {["suspended", "rejected"].includes(row.status) && <Button size="sm" variant="ghost" onClick={() => openAction(row, "reactivate")}>Reactivate</Button>}
              </div>
            ),
          },
        ]}
        empty={<div className="surface p-10 text-center"><Building2 className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No organizations found</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />

      <Modal
        open={modal === "verify"}
        onClose={() => setModal(null)}
        title={`${titleize(verifyAction || "")} organization`}
        description={selected?.name}
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitVerify} loading={verify.isPending} variant={verifyAction === "reject" || verifyAction === "suspend" ? "danger" : "primary"} icon={verifyAction === "reactivate" || verifyAction === "verify" ? CheckCircle2 : undefined}>{titleize(verifyAction || "")}</Button></>}
      >
        <form onSubmit={submitVerify} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          {verifyAction === "verify" && <Alert tone="info">Verifying an insurer automatically creates its insurer profile and notifies all active members.</Alert>}
          {verifyAction === "suspend" && <Alert tone="warning">Suspending an organization hides its offers from customers and blocks provider actions.</Alert>}
          {verifyAction === "reactivate" && <Alert tone="info">Reactivating restores verified status and marketplace access.</Alert>}
          {verifyAction === "reject" && <Textarea label="Rejection reason" required value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain what needs to be corrected." />}
        </form>
      </Modal>

      <Modal
        open={modal === "create"}
        onClose={() => setModal(null)}
        title="New organization"
        description="New organizations start pending verification."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitCreate} loading={create.isPending} icon={Plus}>Create organization</Button></>}
      >
        <form onSubmit={submitCreate} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Organization name" required value={orgForm.name} onChange={(event) => setOrgForm((current) => ({ ...current, name: event.target.value }))} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Type" value={orgForm.organization_type} onChange={(event) => setOrgForm((current) => ({ ...current, organization_type: event.target.value }))} options={ORG_TYPES} />
            <Input label="Registration number" value={orgForm.registration_number} onChange={(event) => setOrgForm((current) => ({ ...current, registration_number: event.target.value }))} />
            <Input label="Email" type="email" value={orgForm.email} onChange={(event) => setOrgForm((current) => ({ ...current, email: event.target.value }))} />
            <Input label="Phone" value={orgForm.phone} onChange={(event) => setOrgForm((current) => ({ ...current, phone: event.target.value }))} />
            <Input label="Website" value={orgForm.website} onChange={(event) => setOrgForm((current) => ({ ...current, website: event.target.value }))} />
            <Input label="Address" value={orgForm.address} onChange={(event) => setOrgForm((current) => ({ ...current, address: event.target.value }))} />
          </div>
          <Textarea label="Description" value={orgForm.description} onChange={(event) => setOrgForm((current) => ({ ...current, description: event.target.value }))} />
        </form>
      </Modal>
    </div>
  );
}
