import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, ClipboardList, Plus } from "lucide-react";
import api, { listData, pageCount } from "../api/client";
import { formatCurrency, formatDate } from "../lib/format";
import { Button, PageHeader, Pagination, SearchInput, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/ui";

export default function Applications() {
  const location = useLocation();
  const isProvider = location.pathname.startsWith("/provider");
  const isDealer = location.pathname.startsWith("/dealer");
  const basePath = isProvider ? "/provider/applications" : isDealer ? "/dealer/applications" : "/app/applications";
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["applications", { isProvider, isDealer, status, search, page }],
    queryFn: async () => (await api.get(`/applications/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["applications", "counts", isProvider, isDealer],
    queryFn: async () => {
      const statuses = ["draft", "submitted", "under_review", "more_info", "approved", "policy_issued", "rejected"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/applications/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);

  return (
    <div>
      <PageHeader
        eyebrow={isProvider ? "Underwriting desk" : isDealer ? "Dealership desk" : "Cover journey"}
        title="Applications"
        description={isProvider
          ? "Review submitted applications and issue policies once premium is verified."
          : isDealer
            ? "Follow applications started from your dealership through policy issuance."
            : "Follow each application from submission through policy issuance."}
        actions={!isProvider && !isDealer ? <Link to="/app/marketplace"><Button variant="secondary" icon={Plus}>Request another quote</Button></Link> : null}
      />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          active={status}
          onChange={(value) => { setStatus(value); setPage(1); }}
          tabs={[
            { value: "", label: "All" },
            { value: "draft", label: "Draft", count: counts.data?.draft },
            { value: "submitted", label: "Submitted", count: counts.data?.submitted },
            { value: "under_review", label: "Review", count: counts.data?.under_review },
            { value: "approved", label: "Approved", count: counts.data?.approved },
            { value: "policy_issued", label: "Issued", count: counts.data?.policy_issued },
          ]}
        />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search application or registration" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          {
            header: "Application",
            cell: (row) => (
              <div>
                <p className="text-xs font-bold text-ink-900">{row.application_number}</p>
                <p className="mt-0.5 text-[10px] text-ink-400">{formatDate(row.created_at)}</p>
              </div>
            ),
          },
          {
            header: "Vehicle",
            cell: (row) => (
              <div>
                <p className="text-xs font-semibold text-ink-800">{row.vehicle_summary?.registration_number}</p>
                <p className="mt-0.5 text-[10px] text-ink-400">{row.vehicle_summary?.make} {row.vehicle_summary?.model}</p>
              </div>
            ),
          },
          { header: "Insurer", cell: (row) => <div><p className="text-xs font-semibold text-ink-800">{row.insurer_name}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.product_name}</p></div> },
          { header: "Premium", cell: (row) => <span className="text-xs font-bold text-ink-900">{formatCurrency(row.premium)}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "", className: "text-right", cell: (row) => <Link to={`${basePath}/${row.id}`} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Review <ArrowRight className="h-3 w-3" /></Link> },
        ]}
        empty={<div className="surface p-10 text-center"><ClipboardList className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No applications yet</p><p className="mt-1 text-xs text-ink-400">{isProvider ? "Submitted customer applications will appear here." : isDealer ? "Applications started from your dealership will appear here." : "Select a quotation to begin your application."}</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
