import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Banknote, CheckCircle2, Clock, ReceiptText } from "lucide-react";
import api, { listData, pageCount } from "../../api/client";
import { formatCurrency, formatDate } from "../../lib/format";
import { Alert, PageHeader, Pagination, Stat, StatusBadge, Tabs } from "../../components/ui";
import { DataTable } from "../../components/DataTable";

export default function Commissions() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const commissions = useQuery({
    queryKey: ["commissions", { status, page }],
    queryFn: async () => (await api.get(`/payments/commissions/?page_size=20&page=${page}${status ? `&status=${status}` : ""}`)).data,
  });
  const all = useQuery({
    queryKey: ["commissions", "summary"],
    queryFn: async () => (await api.get("/payments/commissions/?page_size=200")).data,
  });

  const rows = listData(commissions.data);
  const total = pageCount(commissions.data);
  const everything = listData(all.data);
  const sum = (items) => items.reduce((totalValue, item) => totalValue + Number(item.amount || 0), 0);
  const paid = sum(everything.filter((item) => item.status === "paid"));
  const approved = sum(everything.filter((item) => item.status === "approved"));
  const pending = sum(everything.filter((item) => item.status === "pending"));

  return (
    <div>
      <PageHeader
        eyebrow="Agent earnings"
        title="Commissions"
        description="Track commission earned on policies you place with insurers."
      />

      {all.isError && <div className="mb-4"><Alert>Couldn&apos;t load your commission summary. The list below may still be up to date.</Alert></div>}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={Banknote} label="Total paid" value={formatCurrency(paid)} tone="lime" />
        <Stat icon={CheckCircle2} label="Approved, unpaid" value={formatCurrency(approved)} tone="brand" />
        <Stat icon={Clock} label="Pending" value={formatCurrency(pending)} tone="amber" />
      </div>

      <div className="mb-4">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "pending", label: "Pending" },
          { value: "approved", label: "Approved" },
          { value: "paid", label: "Paid" },
          { value: "cancelled", label: "Cancelled" },
        ]} />
      </div>

      <DataTable
        loading={commissions.isLoading}
        error={commissions.isError}
        onRetry={commissions.refetch}
        rows={rows}
        columns={[
          { header: "Policy", cell: (row) => <div><p className="text-xs font-bold text-ink-900">{row.policy_number}</p><p className="mt-0.5 text-[10px] text-ink-400">{formatDate(row.created_at)}</p></div> },
          { header: "Organization", cell: (row) => <span className="text-xs text-ink-600">{row.organization_name || "—"}</span> },
          { header: "Rate", cell: (row) => <span className="text-xs font-semibold text-ink-700">{Number(row.rate).toFixed(2)}%</span> },
          { header: "Amount", cell: (row) => <span className="text-xs font-bold text-ink-900">{formatCurrency(row.amount)}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          { header: "Paid", cell: (row) => <span className="text-xs text-ink-500">{row.paid_at ? formatDate(row.paid_at) : "—"}</span> },
          { header: "Notes", cell: (row) => <span className="text-xs text-ink-500">{row.notes || "—"}</span> },
        ]}
        empty={<div className="surface p-10 text-center"><ReceiptText className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No commissions yet</p><p className="mt-1 text-xs text-ink-400">Commission appears when an insurer records a policy you placed.</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
