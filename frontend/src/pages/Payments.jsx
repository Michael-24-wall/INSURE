import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { ArrowRight, Banknote, CheckCircle2, CreditCard, ReceiptText, RotateCcw, ShieldCheck } from "lucide-react";
import api, { getErrorMessage, listData, pageCount } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { formatCurrency, formatDateTime, titleize } from "../lib/format";
import { Alert, Button, Input, Modal, PageHeader, Pagination, SearchInput, Stat, StatusBadge, Tabs, Textarea } from "../components/ui";
import { DataTable, DetailItem } from "../components/DataTable";

export default function Payments() {
  const { user } = useAuth();
  const location = useLocation();
  const isProvider = location.pathname.startsWith("/provider");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [verifyForm, setVerifyForm] = useState({ provider_reference: "", notes: "" });
  const [refundForm, setRefundForm] = useState({ amount: "", reason: "" });
  const [receipt, setReceipt] = useState(null);

  const query = useQuery({
    queryKey: ["payments", { isProvider, status, search, page, user: user?.id }],
    queryFn: async () => (await api.get(`/payments/?page_size=20&page=${page}${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`)).data,
  });
  const counts = useQuery({
    queryKey: ["payments", "counts", isProvider, user?.id],
    queryFn: async () => {
      const statuses = ["pending", "processing", "succeeded", "failed", "refunded"];
      const results = await Promise.all(statuses.map(async (value) => {
        const { data } = await api.get(`/payments/?status=${value}&page_size=1`);
        return [value, data.count || 0];
      }));
      return Object.fromEntries(results);
    },
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);
  const pageValue = rows.reduce((sum, payment) => sum + Number(payment.amount || 0), 0);

  const verify = useMutation({
    mutationFn: async () => (await api.post(`/payments/${selected.id}/verify/`, verifyForm)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      toast.push("Payment verified.", "success");
      setModal(null);
      setSelected(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const refund = useMutation({
    mutationFn: async () => (await api.post(`/payments/${selected.id}/refund/`, { amount: Number(refundForm.amount), reason: refundForm.reason })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      toast.push("Refund recorded.", "success");
      setModal(null);
      setSelected(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  async function showReceipt(payment) {
    setError("");
    setSelected(payment);
    try {
      const { data } = await api.get(`/payments/${payment.id}/receipt/`);
      setReceipt(data);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  function openModal(payment, action) {
    setSelected(payment);
    setModal(action);
    setError("");
    setVerifyForm({ provider_reference: payment.provider_reference || "", notes: "" });
    setRefundForm({ amount: payment.amount, reason: "" });
  }

  return (
    <div>
      <PageHeader
        eyebrow={isProvider ? "Collections" : "Billing"}
        title="Payments"
        description={isProvider ? "Verify premium collections and manage refunds. Never confirm funds you have not received." : "Premium payments, receipts and reconciliation status."}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={Banknote} label="Successful" value={counts.data?.succeeded ?? "—"} tone="lime" />
        <Stat icon={CreditCard} label="Awaiting verification" value={counts.data?.pending ?? "—"} tone="amber" />
        <Stat icon={ReceiptText} label="Page value" value={formatCurrency(pageValue)} tone="ink" />
      </div>

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs active={status} onChange={(value) => { setStatus(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "pending", label: "Pending", count: counts.data?.pending },
          { value: "processing", label: "Processing", count: counts.data?.processing },
          { value: "succeeded", label: "Succeeded", count: counts.data?.succeeded },
          { value: "failed", label: "Failed", count: counts.data?.failed },
          { value: "refunded", label: "Refunded", count: counts.data?.refunded },
        ]} />
        <SearchInput value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search reference or receipt" className="w-full lg:w-72" />
      </div>

      {error && <div className="mb-4"><Alert>{error}</Alert></div>}
      {counts.isError && <div className="mb-4"><Alert tone="info">Payment status totals could not be loaded. The list below is still available.</Alert></div>}

      <DataTable
        loading={query.isLoading}
        error={query.isError}
        onRetry={query.refetch}
        rows={rows}
        columns={[
          { header: "Payment", cell: (row) => <div><p className="text-xs font-bold text-ink-900">{row.reference}</p><p className="mt-0.5 text-[10px] text-ink-400">{formatDateTime(row.created_at)}</p></div> },
          { header: "Purpose", cell: (row) => <div><p className="text-xs font-semibold capitalize text-ink-800">{row.purpose?.replace(/_/g, " ")}</p><p className="mt-0.5 text-[10px] text-ink-400">{row.application_number || row.policy_number || row.claim_number || "—"}</p></div> },
          { header: "Payer", cell: (row) => <span className="text-xs text-ink-600">{row.user_name || row.user_email}</span> },
          { header: "Amount", cell: (row) => <span className="text-xs font-bold text-ink-900">{formatCurrency(row.amount)}</span> },
          { header: "Method", cell: (row) => <span className="text-xs capitalize text-ink-600">{row.method}</span> },
          { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
          {
            header: "",
            className: "text-right",
            cell: (row) => (
              <div className="flex justify-end gap-2">
                {isProvider && row.can_verify && <Button size="sm" variant="secondary" onClick={() => openModal(row, "verify")}>Verify</Button>}
                {row.status === "succeeded" && <button onClick={() => showReceipt(row)} className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">Receipt <ArrowRight className="h-3 w-3" /></button>}
              </div>
            ),
          },
        ]}
        empty={<div className="surface p-10 text-center"><ReceiptText className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No payments yet</p><p className="mt-1 text-xs text-ink-400">Payments and receipts will appear here.</p></div>}
      />
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />

      <Modal
        open={modal === "verify"}
        onClose={() => setModal(null)}
        title="Verify payment"
        description="Only confirm after the funds and reference have been independently checked."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={() => verify.mutate()} loading={verify.isPending} disabled={!verifyForm.provider_reference.trim()} icon={CheckCircle2}>Confirm payment</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <div className="rounded-xl bg-ink-50 p-4">
            <p className="text-xs font-bold text-ink-900">{selected?.reference} · {formatCurrency(selected?.amount)}</p>
            <p className="mt-1 text-[11px] text-ink-500">{selected?.user_name} · {selected?.application_number || selected?.policy_number || selected?.claim_number}</p>
          </div>
          <Input label="Provider / transaction reference" required value={verifyForm.provider_reference} onChange={(event) => setVerifyForm((current) => ({ ...current, provider_reference: event.target.value }))} placeholder="M-Pesa receipt or bank transaction ref" />
          <Textarea label="Verification notes" value={verifyForm.notes} onChange={(event) => setVerifyForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Where and when the funds were confirmed" />
          <Alert tone="warning">This action marks the payment successful and can trigger policy issuance. Do not use it without confirmed funds.</Alert>
        </div>
      </Modal>

      <Modal
        open={modal === "refund"}
        onClose={() => setModal(null)}
        title="Create refund"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button variant="danger" onClick={() => refund.mutate()} loading={refund.isPending} disabled={!Number(refundForm.amount) || !refundForm.reason.trim()} icon={RotateCcw}>Record refund</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Refund amount (KES)" type="number" min="0" required value={refundForm.amount} onChange={(event) => setRefundForm((current) => ({ ...current, amount: event.target.value }))} />
          <Textarea label="Reason" required value={refundForm.reason} onChange={(event) => setRefundForm((current) => ({ ...current, reason: event.target.value }))} />
        </div>
      </Modal>

      <Modal
        open={Boolean(receipt)}
        onClose={() => setReceipt(null)}
        title="Payment receipt"
        footer={<><Button variant="secondary" onClick={() => { setReceipt(null); setSelected(null); }}>Close</Button>{isProvider && selected && <Button variant="secondary" icon={RotateCcw} onClick={() => { setReceipt(null); openModal(selected, "refund"); }}>Refund</Button>}</>}
      >
        {receipt && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-emerald-50 p-4 text-emerald-800">
              <ShieldCheck className="h-5 w-5" />
              <p className="mt-2 text-sm font-bold">Payment confirmed</p>
              <p className="text-xs">Receipt {receipt.receipt_number}</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <DetailItem label="Reference">{receipt.reference}</DetailItem>
              <DetailItem label="Amount">{formatCurrency(receipt.amount)}</DetailItem>
              <DetailItem label="Method">{titleize(receipt.method)}</DetailItem>
              <DetailItem label="Purpose">{titleize(receipt.purpose)}</DetailItem>
              <DetailItem label="Paid by">{receipt.paid_by}</DetailItem>
              <DetailItem label="Paid at">{formatDateTime(receipt.paid_at)}</DetailItem>
              <DetailItem label="Provider reference">{receipt.provider_reference || "—"}</DetailItem>
              <DetailItem label="Currency">{receipt.currency}</DetailItem>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
