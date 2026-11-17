import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Download, FileText, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import api, { getErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { formatCurrency, formatDate, titleize } from "../lib/format";
import { Alert, Button, PageLoader, StatusBadge } from "../components/ui";
import { DetailItem } from "../components/DataTable";
import FileDownload from "../components/FileDownload";

export default function PolicyDetail() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const isProvider = location.pathname.startsWith("/provider");
  const isAgent = location.pathname.startsWith("/agent");
  const isCustomer = location.pathname.startsWith("/app");
  const base = isProvider ? "/provider/policies" : isAgent ? "/agent/policies" : "/app/policies";
  const [error, setError] = useState("");

  const query = useQuery({
    queryKey: ["policy", id],
    queryFn: async () => (await api.get(`/policies/${id}/`)).data,
  });
  const claimCount = useQuery({
    queryKey: ["claims", "policy", id],
    queryFn: async () => (await api.get(`/claims/?policy=${id}&page_size=1`)).data,
  });

  const renew = useMutation({
    mutationFn: async () => (await api.post(`/policies/${id}/renew/`)).data,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["quotation-requests"] });
      toast.push("Renewal quotation request created.", "success");
      navigate(`/app/quotes/${data.id}`);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (query.isLoading) return <PageLoader />;
  if (query.isError) return <Alert>Could not load this policy.</Alert>;
  const policy = query.data;
  const expiring = policy.days_to_expiry >= 0 && policy.days_to_expiry <= 30;

  return (
    <div>
      <Link to={base} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to policies</Link>
      <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">{policy.policy_number}</p>
            <StatusBadge status={policy.status} />
          </div>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{policy.vehicle_summary?.registration_number} · {policy.insurer_name}</h1>
          <p className="mt-2 text-sm text-ink-500">{policy.product_name} · {formatDate(policy.start_date)} to {formatDate(policy.end_date)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {policy.certificate && (
            <FileDownload
              url={policy.certificate}
              filename={`${policy.policy_number}.pdf`}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-ink-200 bg-white px-4 text-sm font-semibold text-ink-800 transition hover:bg-ink-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/20"
            >
              <Download className="h-4 w-4" /> Certificate
            </FileDownload>
          )}
          {isCustomer && policy.status === "active" && <Button icon={RefreshCw} onClick={() => renew.mutate()} loading={renew.isPending}>Request renewal</Button>}
          {isCustomer && <Link to="/app/claims"><Button variant="danger-soft" icon={TriangleAlert}>Make a claim</Button></Link>}
        </div>
      </div>

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}
      {expiring && <div className="mb-5"><Alert tone="warning" title="Policy expiring soon">This policy expires in {policy.days_to_expiry} days. Request a renewal quotation to avoid a coverage gap.</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="surface overflow-hidden">
          <div className="relative bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6 text-white">
            <div className="landing-grid absolute inset-0 opacity-25" />
            <div className="relative flex items-start justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">Insurance policy</p>
                <p className="mt-2 font-display text-2xl font-bold tracking-tight">{policy.policy_number}</p>
                <p className="mt-1 text-sm text-white/55">{policy.vehicle_summary?.make} {policy.vehicle_summary?.model} · {policy.vehicle_summary?.year}</p>
              </div>
              <ShieldCheck className="h-10 w-10 text-lime-300" />
            </div>
          </div>
          <div className="grid gap-5 p-6 sm:grid-cols-3">
            <DetailItem label="Policyholder">{policy.customer_name}</DetailItem>
            <DetailItem label="Product">{policy.product_name}</DetailItem>
            <DetailItem label="Insurer">{policy.insurer_name}</DetailItem>
            <DetailItem label="Premium">{formatCurrency(policy.premium)}</DetailItem>
            <DetailItem label="Sum insured">{formatCurrency(policy.sum_insured)}</DetailItem>
            <DetailItem label="Excess">{formatCurrency(policy.excess_amount)}</DetailItem>
            <DetailItem label="Start date">{formatDate(policy.start_date)}</DetailItem>
            <DetailItem label="End date">{formatDate(policy.end_date)}</DetailItem>
            <DetailItem label="Issued on">{formatDate(policy.issued_at)}</DetailItem>
            <DetailItem label="Provider reference">{policy.provider_reference || "—"}</DetailItem>
            <DetailItem label="Claims filed">{claimCount.data?.count ?? policy.claim_count ?? 0}</DetailItem>
            <DetailItem label="Days to expiry">{policy.days_to_expiry}</DetailItem>
          </div>
        </div>

        <div className="space-y-4">
          <div className="surface p-5">
            <h2 className="font-display text-base font-bold text-ink-950">Cover at a glance</h2>
            <div className="mt-4 space-y-3 text-xs text-ink-500">
              <p className="flex items-start gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> {titleize(policy.product_name || "")} motor cover with a {formatCurrency(policy.excess_amount)} excess.</p>
              <p className="flex items-start gap-2"><FileText className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" /> Keep your certificate available in the vehicle and on your phone.</p>
              <p className="flex items-start gap-2"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" /> Report incidents promptly and do not admit liability or settle privately.</p>
            </div>
          </div>
          {isProvider && (
            <div className="surface p-5">
              <h2 className="font-display text-base font-bold text-ink-950">Underwriting data</h2>
              <div className="mt-4 space-y-3">
                <DetailItem label="Application">{policy.application}</DetailItem>
                <DetailItem label="Insurer ID">{policy.insurer_id}</DetailItem>
                <DetailItem label="Claims count">{policy.claim_count}</DetailItem>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
