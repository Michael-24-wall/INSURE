import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, FileSearch, Plus } from "lucide-react";
import api, { listData, pageCount } from "../api/client";
import { formatCurrency, formatDate, titleize } from "../lib/format";
import { PRODUCT_CATEGORIES } from "../lib/constants";
import { Button, Input, PageHeader, Pagination, SearchInput, Select, StatusBadge, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";

export default function Quotations() {
  const location = useLocation();
  const isProvider = location.pathname.startsWith("/provider");
  const isDealer = location.pathname.startsWith("/dealer");
  const basePath = isProvider ? "/provider/quotes" : isDealer ? "/dealer/quotes" : "/app/quotes";
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [dealership, setDealership] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [page, setPage] = useState(1);

  const partnerships = useQuery({
    queryKey: ["partnerships", "quotation-filter"],
    queryFn: async () => (await api.get("/business-network/partnerships/?page_size=100")).data,
    enabled: isProvider,
  });
  const dealershipOptions = listData(partnerships.data)
    .map((item) => ({ value: item.dealership_id, label: item.dealership_name }))
    .filter((item, index, all) => item.value && all.findIndex((entry) => entry.value === item.value) === index);

  const params = new URLSearchParams({ page_size: "20", page: String(page) });
  if (status) params.set("status", status);
  if (search) params.set("search", search);
  if (category) params.set("coverage_type", category);
  if (isProvider && dealership) params.set("dealership", dealership);
  if (fromDate) params.set("created_after", fromDate);
  if (toDate) params.set("created_before", toDate);

  const query = useQuery({
    queryKey: ["quotation-requests", { isProvider, isDealer, status, search, category, dealership, fromDate, toDate, page }],
    queryFn: async () => (await api.get(`/quotation-requests/?${params.toString()}`)).data,
  });
  const counts = useQuery({
    queryKey: ["quotation-requests", "counts", isProvider, isDealer],
    queryFn: async () => {
      const statuses = ["pending", "under_review", "more_info", "quoted", "selected", "converted", "rejected", "expired"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/quotation-requests/?status=${value}&page_size=1`);
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
        eyebrow={isProvider ? "Insurer inbox" : isDealer ? "Dealership desk" : "Your cover search"}
        title={isProvider ? "Quote requests" : isDealer ? "Quotation requests" : "Quotations"}
        description={isProvider
          ? "Dealer and customer requests directed to your team, plus marketplace requests you have quoted."
          : isDealer
            ? "Track requests raised for your customers and compare insurer offers."
            : "Track requests and compare offers from verified insurers."}
        actions={!isProvider && !isDealer ? <Link to="/app/marketplace"><Button icon={Plus}>New quote request</Button></Link> : null}
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          active={status}
          onChange={(value) => { setStatus(value); setPage(1); }}
          tabs={[
            { value: "", label: "All" },
            { value: "pending", label: "Pending", count: counts.data?.pending },
            { value: "under_review", label: "In review", count: counts.data?.under_review },
            { value: "more_info", label: "Info needed", count: counts.data?.more_info },
            { value: "quoted", label: "Quoted", count: counts.data?.quoted },
            { value: "selected", label: "Selected", count: counts.data?.selected },
            { value: "converted", label: "Converted", count: counts.data?.converted },
            { value: "rejected", label: "Rejected", count: counts.data?.rejected },
            { value: "expired", label: "Expired", count: counts.data?.expired },
          ]}
        />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search request, customer or registration" className="w-full lg:w-72" />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Select label="Cover type" placeholder="All cover types" value={category} onChange={(event) => { setCategory(event.target.value); setPage(1); }} options={PRODUCT_CATEGORIES} />
        {isProvider && <Select label="Dealership" placeholder="All dealerships" value={dealership} onChange={(event) => { setDealership(event.target.value); setPage(1); }} options={dealershipOptions} />}
        <Input label="Created from" type="date" value={fromDate} onChange={(event) => { setFromDate(event.target.value); setPage(1); }} />
        <Input label="Created to" type="date" value={toDate} onChange={(event) => { setToDate(event.target.value); setPage(1); }} />
      </div>

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          {
            header: "Request",
            cell: (row) => (
              <div>
                <p className="text-xs font-bold text-ink-900">{row.request_number}</p>
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
          { header: "Cover", cell: (row) => <span className="text-xs text-ink-600">{titleize(row.coverage_type)}</span> },
          { header: "Sum insured", cell: (row) => <span className="text-xs font-semibold text-ink-800">{formatCurrency(row.sum_insured)}</span> },
          {
            header: "Quotes",
            cell: (row) => (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-ink-700">
                {row.quotation_count || 0}
                {row.lowest_premium && <span className="text-[10px] font-normal text-ink-400">from {formatCurrency(row.lowest_premium)}</span>}
              </span>
            ),
          },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "Updated", cell: (row) => <span className="text-xs text-ink-500">{formatDate(row.updated_at)}</span> },
          {
            header: "",
            className: "text-right",
            cell: (row) => <Link to={`${basePath}/${row.id}`} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Open <ArrowRight className="h-3 w-3" /></Link>,
          },
        ]}
        empty={<div className="surface p-10 text-center"><FileSearch className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No quote requests yet</p><p className="mt-1 text-xs text-ink-400">{isProvider ? "Dealer and customer requests will appear here." : isDealer ? "Raise a quotation request from your inventory to get started." : "Explore available insurance lines and request a live quote where supported."}</p>{!isProvider && !isDealer && <Link to="/app/marketplace"><Button size="sm" className="mt-4">Explore insurance</Button></Link>}</div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
