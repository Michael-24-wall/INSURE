import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Pencil, Shield, UserCheck, Users as UsersIcon } from "lucide-react";
import api, { getErrorMessage, listData, pageCount } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { ROLE_LABELS, ROLES } from "../../lib/constants";
import { formatDate, initials, titleize } from "../../lib/format";
import { Alert, Badge, Button, Input, Modal, PageHeader, Pagination, SearchInput, Select, Stat, Tabs } from "../../components/ui";
import { DataTable } from "../../components/DataTable";

export default function AdminUsers() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [role, setRole] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");

  const users = useQuery({
    queryKey: ["admin-users", { role, search, page }],
    queryFn: async () => (await api.get(`/auth/users/?page_size=20&page=${page}${role ? `&role=${role}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["admin-users", "counts"],
    queryFn: async () => {
      const roleValues = Object.values(ROLES);
      const results = await Promise.all(roleValues.map(async (value) => {
        const { data } = await api.get(`/auth/users/?role=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const save = useMutation({
    mutationFn: async () => (await api.patch(`/auth/users/${selected.id}/manage/`, form)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.push("User updated.", "success");
      setSelected(null);
      setForm(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const kycReview = useMutation({
    mutationFn: async ({ action }) => (await api.post(`/auth/users/${selected.id}/kyc-review/`, { action })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.push("KYC review saved.", "success");
      setSelected(null);
      setForm(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const rows = listData(users.data);
  const total = pageCount(users.data);
  const totalUsers = Object.values(counts.data || {}).reduce((sum, value) => sum + value, 0);

  function openUser(user) {
    setError("");
    setSelected(user);
    setForm({
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      phone: user.phone || "",
      role: user.role,
      is_active: user.is_active,
      email_verified: user.email_verified,
    });
  }

  function submit(event) {
    event.preventDefault();
    setError("");
    save.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Platform administration"
        title="Users"
        description="Manage accounts, roles and access across the platform."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={UsersIcon} label="Total users" value={totalUsers || "—"} />
        <Stat icon={Mail} label="Customers" value={counts.data?.customer ?? "—"} tone="blue" />
        <Stat icon={Shield} label="Provider staff" value={(counts.data?.provider_admin || 0) + (counts.data?.provider_staff || 0)} tone="amber" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={role} onChange={(value) => { setRole(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "customer", label: "Customers", count: counts.data?.customer },
          { value: "provider_admin", label: "Provider admins", count: counts.data?.provider_admin },
          { value: "claims_officer", label: "Claims", count: counts.data?.claims_officer },
          { value: "inspector", label: "Inspectors", count: counts.data?.inspector },
          { value: "agent", label: "Agents", count: counts.data?.agent },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search name, email or phone" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={users.isLoading}
        error={users.isError}
        onRetry={users.refetch}
        rows={rows}
        columns={[
          {
            header: "User",
            cell: (row) => (
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink-100 text-xs font-bold text-ink-600">{initials(row.full_name || row.email)}</span>
                <div>
                  <p className="text-xs font-bold text-ink-900">{row.full_name || "Unnamed"}</p>
                  <p className="mt-0.5 text-[10px] text-ink-400">{row.email}</p>
                </div>
              </div>
            ),
          },
          { header: "Role", cell: (row) => <Badge tone="brand">{ROLE_LABELS[row.role] || titleize(row.role)}</Badge> },
          { header: "Contact", cell: (row) => <span className="text-xs text-ink-600">{row.phone || "—"}</span> },
          { header: "Verified", cell: (row) => row.email_verified ? <Badge tone="green">Verified</Badge> : <Badge tone="amber">Unverified</Badge> },
          { header: "KYC", cell: (row) => row.kyc_status === "verified" ? <Badge tone="green">Verified</Badge> : row.kyc_status === "pending" ? <Badge tone="amber">Pending</Badge> : row.kyc_status === "rejected" ? <Badge tone="red">Rejected</Badge> : <span className="text-xs text-ink-400">—</span> },
          { header: "Status", cell: (row) => row.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Disabled</Badge> },
          { header: "Joined", cell: (row) => <span className="text-xs text-ink-500">{formatDate(row.created_at)}</span> },
          { header: "", className: "text-right", cell: (row) => <Button size="sm" variant="ghost" icon={Pencil} onClick={() => openUser(row)}>Manage</Button> },
        ]}
        empty={<div className="surface p-10 text-center"><UsersIcon className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No users found</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />

      <Modal
        open={Boolean(selected)}
        onClose={() => { setSelected(null); setForm(null); }}
        title="Manage user"
        description={selected?.email}
        footer={<><Button variant="secondary" onClick={() => setSelected(null)}>Cancel</Button><Button onClick={submit} loading={save.isPending} icon={UserCheck}>Save changes</Button></>}
      >
        {form && (
          <form onSubmit={submit} className="space-y-4">
            {error && <Alert>{error}</Alert>}
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="First name" value={form.first_name} onChange={(event) => setForm((current) => ({ ...current, first_name: event.target.value }))} />
              <Input label="Last name" value={form.last_name} onChange={(event) => setForm((current) => ({ ...current, last_name: event.target.value }))} />
            </div>
            <Input label="Phone" value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} />
            <Select label="Role" value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))} options={Object.values(ROLES).map((value) => ({ value, label: ROLE_LABELS[value] }))} />
            <label className="flex items-center gap-2 text-sm text-ink-700"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} className="h-4 w-4 rounded border-ink-300 text-brand-600" /> Account can sign in</label>
            <label className="flex items-center gap-2 text-sm text-ink-700"><input type="checkbox" checked={form.email_verified} onChange={(event) => setForm((current) => ({ ...current, email_verified: event.target.checked }))} className="h-4 w-4 rounded border-ink-300 text-brand-600" /> Email verified</label>
            {!form.is_active && <Alert tone="warning">Disabling an account prevents sign-in but preserves records and audit history.</Alert>}
            {selected?.role === "customer" && selected?.kyc_status && selected.kyc_status !== "verified" && (
              <div className="rounded-xl border border-ink-100 p-4">
                <p className="text-xs font-bold uppercase tracking-[0.1em] text-ink-400">KYC review</p>
                <p className="mt-1 text-xs text-ink-500">Status: <span className="font-semibold">{selected.kyc_status}</span></p>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="brand" onClick={() => kycReview.mutate({ action: "approve" })} loading={kycReview.isPending}>Approve</Button>
                  <Button size="sm" variant="danger-soft" onClick={() => kycReview.mutate({ action: "reject" })} loading={kycReview.isPending}>Reject</Button>
                </div>
              </div>
            )}
          </form>
        )}
      </Modal>
    </div>
  );
}
