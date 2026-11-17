import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, CalendarCheck, Car, ClipboardCheck, MapPin } from "lucide-react";
import api, { listData, pageCount } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { formatDateTime, titleize } from "../../lib/format";
import { SectionBanner } from "../../components/Hero";
import { Pagination, SearchInput, Stat, Tabs, StatusBadge } from "../../components/ui";
import { DataTable } from "../../components/DataTable";

export default function Inspections() {
  const { user } = useAuth();
  const location = useLocation();
  const isInspector = user?.role === "inspector" || location.pathname.startsWith("/inspector");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["inspections", { status, search, page, inspector: isInspector }],
    queryFn: async () => (await api.get(`/inspections/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["inspections", "counts", isInspector],
    queryFn: async () => {
      const statuses = ["requested", "scheduled", "in_progress", "completed", "cancelled"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/inspections/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);

  return (
    <div>
      <SectionBanner
        image="/images/hero-inspection.svg"
        alt="Vehicle inspection"
        eyebrow={isInspector ? "Field work" : "Vehicle assessment"}
        title={isInspector ? "My inspections" : "Inspections"}
        text={isInspector ? "Scheduled visits, damage recording and inspection reports." : "Pre-insurance, renewal and claim assessment inspections."}
        className="mb-6"
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={CalendarCheck} label="Scheduled" value={counts.data?.scheduled ?? "—"} tone="amber" />
        <Stat icon={ClipboardCheck} label="In progress" value={counts.data?.in_progress ?? "—"} tone="brand" />
        <Stat icon={Car} label="Completed" value={counts.data?.completed ?? "—"} tone="lime" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "requested", label: "Requested", count: counts.data?.requested },
          { value: "scheduled", label: "Scheduled", count: counts.data?.scheduled },
          { value: "in_progress", label: "In progress", count: counts.data?.in_progress },
          { value: "completed", label: "Completed", count: counts.data?.completed },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search inspection or registration" className="w-full lg:w-72" />
      </div>

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          { header: "Inspection", cell: (row) => <div><p className="text-xs font-bold text-ink-900">{row.inspection_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{titleize(row.inspection_type)}</p></div> },
          { header: "Vehicle", cell: (row) => <div><p className="text-xs font-semibold text-ink-800">{row.vehicle_summary?.registration_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.vehicle_summary?.make} {row.vehicle_summary?.model}</p></div> },
          { header: "Inspector", cell: (row) => <span className="text-xs text-ink-600">{row.inspector_name || "Unassigned"}</span> },
          { header: "Schedule", cell: (row) => <div><p className="text-xs text-ink-600">{row.scheduled_at ? formatDateTime(row.scheduled_at) : "Not scheduled"}</p>{row.location && <p className="mt-0.5 flex items-center gap-1 text-[10px] text-ink-400"><MapPin className="h-3 w-3" />{row.location}</p>}</div> },
          { header: "Damages", cell: (row) => <span className="text-xs font-semibold text-ink-700">{row.damage_count}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "", className: "text-right", cell: (row) => <Link to={`/inspections/${row.id}`} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Open <ArrowRight className="h-3 w-3" /></Link> },
        ]}
        empty={<div className="surface p-10 text-center"><CalendarCheck className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No inspections</p><p className="mt-1 text-xs text-ink-400">Inspections requested from vehicles will appear here.</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
