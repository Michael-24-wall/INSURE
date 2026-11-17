import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Plus, TriangleAlert } from "lucide-react";
import api, { getErrorMessage, listData, pageCount } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { CLAIM_TYPES } from "../../lib/constants";
import { formatCurrency, formatDate, todayISO } from "../../lib/format";
import { SectionBanner } from "../../components/Hero";
import { Alert, Button, Input, Modal, Pagination, SearchInput, Select, Stat, Tabs, Textarea } from "../../components/ui";
import { DataTable } from "../../components/DataTable";
import { StatusBadge } from "../../components/ui";

export default function Claims() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const isCustomer = user?.role === "customer";
  const claimDetailPath = (claimId) => `${isCustomer ? "/app/claims" : "/claims"}/${claimId}`;
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    policy: "",
    claim_type: "accident",
    incident_date: todayISO(0),
    incident_time: "",
    location: "",
    description: "",
    police_report_number: "",
    amount_claimed: "",
  });

  const query = useQuery({
    queryKey: ["claims", { status, search, page, role: user?.role }],
    queryFn: async () => (await api.get(`/claims/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["claims", "counts", user?.role],
    queryFn: async () => {
      const statuses = ["submitted", "under_review", "inspection_scheduled", "approved", "settled", "rejected"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/claims/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });
  const policies = useQuery({
    queryKey: ["policies", "claim-options"],
    queryFn: async () => (await api.get("/policies/?status=active&page_size=100")).data,
    enabled: isCustomer && open,
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);
  const policyRows = listData(policies.data);

  const createClaim = useMutation({
    mutationFn: async () => {
      const payload = { ...form, amount_claimed: Number(form.amount_claimed) };
      if (!payload.incident_time) delete payload.incident_time;
      return (await api.post("/claims/", payload)).data;
    },
    onSuccess: (claim) => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      toast.push("Claim submitted.", "success");
      setOpen(false);
      navigate(claimDetailPath(claim.id));
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  function submit(event) {
    event.preventDefault();
    setError("");
    createClaim.mutate();
  }

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <div>
      <SectionBanner
        image="/images/hero-claims.svg"
        alt="Claims assessment"
        eyebrow={isCustomer ? "Claims support" : "Claims workspace"}
        title={isCustomer ? "Your claims" : "Claims"}
        text={isCustomer ? "Report an incident, upload evidence and track the assessment." : "Review, assess, approve and settle motor claims."}
        actions={isCustomer ? <Button icon={Plus} onClick={() => { setError(""); setOpen(true); }}>Submit a claim</Button> : null}
        className="mb-6"
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={TriangleAlert} label="Open claims" value={(counts.data?.submitted || 0) + (counts.data?.under_review || 0) + (counts.data?.inspection_scheduled || 0)} tone="amber" />
        <Stat icon={TriangleAlert} label="Approved" value={counts.data?.approved ?? "—"} tone="brand" />
        <Stat icon={TriangleAlert} label="Settled" value={counts.data?.settled ?? "—"} tone="lime" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "submitted", label: "Submitted", count: counts.data?.submitted },
          { value: "under_review", label: "Review", count: counts.data?.under_review },
          { value: "inspection_scheduled", label: "Inspection", count: counts.data?.inspection_scheduled },
          { value: "approved", label: "Approved", count: counts.data?.approved },
          { value: "settled", label: "Settled", count: counts.data?.settled },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search claim, policy or location" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          { header: "Claim", cell: (row) => <div><p className="text-xs font-bold text-ink-900">{row.claim_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{formatDate(row.incident_date)}</p></div> },
          { header: "Vehicle", cell: (row) => <div><p className="text-xs font-semibold text-ink-800">{row.vehicle_summary?.registration_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.insurer_name}</p></div> },
          { header: "Type", cell: (row) => <span className="text-xs capitalize text-ink-600">{row.claim_type?.replace(/_/g, " ")}</span> },
          { header: "Claimed", cell: (row) => <span className="text-xs font-bold text-ink-900">{formatCurrency(row.amount_claimed)}</span> },
          { header: "Approved", cell: (row) => <span className="text-xs font-semibold text-ink-700">{row.approved_amount ? formatCurrency(row.approved_amount) : "—"}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "", className: "text-right", cell: (row) => <Link to={claimDetailPath(row.id)} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Open <ArrowRight className="h-3 w-3" /></Link> },
        ]}
        empty={<div className="surface p-10 text-center"><TriangleAlert className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No claims found</p><p className="mt-1 text-xs text-ink-400">{isCustomer ? "If something happens, submit a claim and we will guide you through it." : "Claims matching this filter will appear here."}</p>{isCustomer && <Button size="sm" className="mt-4" onClick={() => setOpen(true)}>Submit a claim</Button>}</div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Submit a claim"
        description="Provide accurate incident details. You can upload evidence after submitting."
        size="lg"
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={submit} loading={createClaim.isPending}>Submit claim</Button></>}
      >
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select
            label="Policy"
            required
            placeholder={policyRows.length ? "Select the policy covering this incident" : "No active policies found"}
            value={form.policy}
            onChange={(event) => update("policy", event.target.value)}
            options={policyRows.map((policy) => ({ value: policy.id, label: `${policy.policy_number} · ${policy.vehicle_summary?.registration_number} · ${policy.insurer_name}` }))}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Claim type" required value={form.claim_type} onChange={(event) => update("claim_type", event.target.value)} options={CLAIM_TYPES} />
            <Input label="Amount claimed (KES)" type="number" min="1" required value={form.amount_claimed} onChange={(event) => update("amount_claimed", event.target.value)} />
            <Input label="Incident date" type="date" required max={todayISO(0)} value={form.incident_date} onChange={(event) => update("incident_date", event.target.value)} />
            <Input label="Incident time" type="time" value={form.incident_time} onChange={(event) => update("incident_time", event.target.value)} />
          </div>
          <Input label="Location" required value={form.location} onChange={(event) => update("location", event.target.value)} placeholder="Road, town or landmark" />
          <Textarea label="What happened?" required value={form.description} onChange={(event) => update("description", event.target.value)} placeholder="Describe the incident factually. Do not admit liability." />
          <Input label="Police report number" value={form.police_report_number} onChange={(event) => update("police_report_number", event.target.value)} placeholder="Optional" />
        </form>
      </Modal>
    </div>
  );
}
