import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, Plus, ReceiptText, UserPlus, Wallet } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, formatDate } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, Button, Modal, PageLoader, SectionTitle, Stat, StatusBadge } from "../../components/ui";

export default function AgentDashboard() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [error, setError] = useState("");

  const commissions = useQuery({
    queryKey: ["commissions", "agent"],
    queryFn: async () => (await api.get("/payments/commissions/?page_size=100&ordering=-created_at")).data,
  });

  const requests = useQuery({
    queryKey: ["agent", "quotation-requests"],
    queryFn: async () => (await api.get("/quotation-requests/?page_size=100")).data,
    enabled: open,
  });

  const quotes = useQuery({
    queryKey: ["agent", "quotes", selectedRequest?.id],
    queryFn: async () => (await api.get(`/quotation-requests/${selectedRequest.id}/quotations/`)).data,
    enabled: Boolean(open && selectedRequest),
  });

  const create = useMutation({
    mutationFn: async () => (await api.post("/applications/agent-create/", {
      quotation: selectedQuote.id,
      customer: selectedRequest.customer,
    })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["commissions", "agent"] });
      toast.push("Application created for the customer.", "success");
      setOpen(false);
      setSelectedRequest(null);
      setSelectedQuote(null);
      setError("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (commissions.isLoading) return <PageLoader />;
  if (commissions.isError) {
    return (
      <div className="surface p-5">
        <Alert title="We couldn't load your commissions.">Please refresh the page to try again.</Alert>
      </div>
    );
  }
  const rows = listData(commissions.data);
  const total = (status) => rows.filter((row) => row.status === status).reduce((sum, row) => sum + Number(row.amount), 0);
  const requestRows = listData(requests.data).filter((req) => ["pending", "quoted", "selected"].includes(req.status));
  const quoteRows = listData(quotes.data);

  return (
    <div>
      <DashboardHero
        image="/images/hero-marketplace.svg"
        alt="Vehicles in a lineup"
        eyebrow="Agent workspace"
        title="Grow your insurance business."
        text="See every policy-linked commission and its payment status."
        actions={<Button icon={Plus} onClick={() => { setOpen(true); setError(""); }}>Start application</Button>}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={Wallet} label="Pending" value={formatCurrency(total("pending"))} hint={`${rows.filter((r) => r.status === "pending").length} records`} tone="amber" />
        <Stat icon={ReceiptText} label="Approved" value={formatCurrency(total("approved"))} hint={`${rows.filter((r) => r.status === "approved").length} records`} />
        <Stat icon={Wallet} label="Paid" value={formatCurrency(total("paid"))} hint={`${rows.filter((r) => r.status === "paid").length} records`} tone="lime" />
      </div>

      <div className="mt-8">
        <SectionTitle title="Commission history" action={<Link to="/agent/commissions" className="text-xs font-bold text-brand-700 hover:underline">View all <ArrowRight className="ml-1 inline h-3 w-3" /></Link>} />
        <div className="surface divide-y divide-ink-100">
          {rows.slice(0, 8).map((row) => (
            <div key={row.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold text-ink-900">{row.policy_number}</p>
                <p className="mt-1 text-[11px] text-ink-400">{row.organization_name || "Platform"} · {row.rate}% · {formatDate(row.created_at)}</p>
              </div>
              <div className="flex items-center gap-4">
                <p className="text-sm font-bold text-ink-950">{formatCurrency(row.amount)}</p>
                <StatusBadge status={row.status} />
              </div>
            </div>
          ))}
          {!rows.length && <p className="p-6 text-sm text-ink-500">Commissions will appear once a provider records them against your policies.</p>}
        </div>
      </div>

      <Modal
        open={open}
        onClose={() => { setOpen(false); setSelectedRequest(null); setSelectedQuote(null); }}
        title="Start an application"
        description="Choose a customer's quotation request, then the insurer offer to convert into an application on their behalf."
        footer={selectedQuote && <><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => create.mutate()} loading={create.isPending} icon={UserPlus}>Create application</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          {!selectedRequest ? (
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-[0.1em] text-ink-400">Open quotation requests</p>
              {requests.isLoading && <p className="text-sm text-ink-500">Loading…</p>}
              {requests.isError && <Alert>Could not load quotation requests. Close and reopen to retry.</Alert>}
              {!requests.isLoading && !requests.isError && !requestRows.length && <Alert tone="info">No open quotation requests right now.</Alert>}
              {requestRows.map((req) => (
                <button key={req.id} onClick={() => { setSelectedQuote(null); setSelectedRequest(req); }} className="flex w-full items-center justify-between rounded-xl border border-ink-100 p-3 text-left hover:border-brand-300">
                  <div>
                    <p className="text-xs font-bold text-ink-900">{req.customer_name || req.customer_email}</p>
                    <p className="mt-0.5 text-[10px] text-ink-400">{req.vehicle_summary?.registration_number} · {req.coverage_type?.replace(/_/g, " ")}</p>
                  </div>
                  <span className="text-[10px] font-semibold text-brand-700">{req.quotation_count || 0} offers</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold uppercase tracking-[0.1em] text-ink-400">Select an offer</p>
                <button onClick={() => { setSelectedRequest(null); setSelectedQuote(null); }} className="text-xs font-bold text-brand-700 hover:underline">Back</button>
              </div>
              <div className="rounded-lg bg-ink-50 p-3">
                <p className="text-xs font-bold text-ink-900">{selectedRequest.customer_name || selectedRequest.customer_email}</p>
                <p className="mt-0.5 text-[10px] text-ink-400">{selectedRequest.vehicle_summary?.registration_number}</p>
              </div>
              {quotes.isLoading && <p className="text-sm text-ink-500">Loading offers…</p>}
              {quotes.isError && <Alert>Could not load offers. Go back and select the request again.</Alert>}
              {!quotes.isLoading && !quotes.isError && !quoteRows.length && <Alert tone="info">No offers available for this request.</Alert>}
              {quoteRows.map((quote) => (
                <button key={quote.id} onClick={() => setSelectedQuote(quote)} className={`flex w-full items-center justify-between rounded-xl border p-3 text-left ${selectedQuote?.id === quote.id ? "border-brand-500 bg-brand-50" : "border-ink-100 hover:border-brand-300"}`}>
                  <div>
                    <p className="text-xs font-bold text-ink-900">{quote.insurer_name} · {quote.product_name}</p>
                    <p className="mt-0.5 text-[10px] text-ink-400">Quote {quote.quotation_number}</p>
                  </div>
                  <p className="text-sm font-bold text-ink-950">{formatCurrency(quote.premium)}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
