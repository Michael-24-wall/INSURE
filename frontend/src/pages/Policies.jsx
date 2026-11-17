import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, ShieldCheck } from "lucide-react";
import api, { listData, pageCount } from "../api/client";
import { formatCurrency, formatDate } from "../lib/format";
import { Button, PageHeader, Pagination, SearchInput, Stat, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/ui";

export default function Policies() {
  const location = useLocation();
  const isProvider = location.pathname.startsWith("/provider");
  const isAgent = location.pathname.startsWith("/agent");
  const isCustomer = location.pathname.startsWith("/app");
  const base = isProvider ? "/provider/policies" : isAgent ? "/agent/policies" : "/app/policies";
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["policies", { isProvider, status, search, page }],
    queryFn: async () => (await api.get(`/policies/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["policies", "counts", isProvider],
    queryFn: async () => {
      const statuses = ["active", "expired", "cancelled", "lapsed"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/policies/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);
  const premiumTotal = rows.reduce((sum, policy) => sum + Number(policy.premium || 0), 0);

  return (
    <div>
      <PageHeader
        eyebrow={isProvider ? "Policy register" : isAgent ? "Client book" : "Your protection"}
        title="Policies"
        description={isProvider ? "Issued policies for your insurer, including renewals and claims exposure." : isAgent ? "Policies linked to your agency book and commission records." : "Your active and historical motor policies in one place."}
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={ShieldCheck} label="Active policies" value={counts.data?.active ?? "—"} tone="lime" />
        <Stat icon={ShieldCheck} label="Total records" value={total} tone="brand" />
        <Stat icon={ShieldCheck} label="Page premium" value={formatCurrency(premiumTotal)} tone="ink" />
      </div>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "active", label: "Active", count: counts.data?.active },
          { value: "expired", label: "Expired", count: counts.data?.expired },
          { value: "cancelled", label: "Cancelled", count: counts.data?.cancelled },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search policy or registration" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          { header: "Policy", cell: (row) => <div><p className="text-xs font-bold text-ink-900">{row.policy_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.insurer_name}</p></div> },
          { header: "Vehicle", cell: (row) => <div><p className="text-xs font-semibold text-ink-800">{row.vehicle_summary?.registration_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.vehicle_summary?.make} {row.vehicle_summary?.model}</p></div> },
          { header: "Cover period", cell: (row) => <span className="text-xs text-ink-600">{formatDate(row.start_date)} – {formatDate(row.end_date)}</span> },
          { header: "Premium", cell: (row) => <span className="text-xs font-bold text-ink-900">{formatCurrency(row.premium)}</span> },
          { header: "Expiry", cell: (row) => <span className={`text-xs font-semibold ${row.days_to_expiry <= 30 ? "text-amber-600" : "text-ink-600"}`}>{row.days_to_expiry < 0 ? "Expired" : `${row.days_to_expiry} days`}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "", className: "text-right", cell: (row) => <Link to={`${base}/${row.id}`} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Open <ArrowRight className="h-3 w-3" /></Link> },
        ]}
        empty={<div className="surface p-10 text-center"><ShieldCheck className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No policies yet</p><p className="mt-1 text-xs text-ink-400">{isProvider ? "Issued policies will appear here." : isAgent ? "Policies linked to your book will appear here." : "A policy appears after an application is approved and paid."}</p>{isCustomer && <Link to="/app/marketplace"><Button size="sm" className="mt-4">Get covered</Button></Link>}</div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
