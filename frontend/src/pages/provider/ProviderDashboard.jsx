import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CalendarCheck,
  ClipboardList,
  FileSearch,
  Package,
  ShieldCheck,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import api, { listData } from "../../api/client";
import { formatCurrency, formatDateTime, titleize } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, Button, Input, PageLoader, SectionTitle, Stat, StatusBadge } from "../../components/ui";

export default function ProviderDashboard() {
  const [period, setPeriod] = useState({ start: "", end: "" });
  const dashboard = useQuery({
    queryKey: ["dashboard", "provider"],
    queryFn: async () => (await api.get("/analytics/dashboard/")).data,
  });
  const applications = useQuery({
    queryKey: ["applications", "provider-dashboard"],
    queryFn: async () => (await api.get("/applications/?page_size=6&ordering=-created_at")).data,
  });
  const claims = useQuery({
    queryKey: ["claims", "provider-dashboard"],
    queryFn: async () => (await api.get("/claims/?page_size=5&ordering=-created_at")).data,
  });
  const inspections = useQuery({
    queryKey: ["inspections", "provider-dashboard"],
    queryFn: async () => (await api.get("/inspections/?page_size=5&ordering=scheduled_at")).data,
  });
  const financial = useQuery({
    queryKey: ["finance", "provider", period],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (period.start) params.set("start", period.start);
      if (period.end) params.set("end", period.end);
      const query = params.toString();
      return (await api.get(`/finance/dashboard/${query ? `?${query}` : ""}`)).data;
    },
  });

  if (dashboard.isLoading || financial.isLoading || applications.isLoading || claims.isLoading || inspections.isLoading) {
    return <PageLoader />;
  }
  if (dashboard.isError || financial.isError || applications.isError || claims.isError || inspections.isError) {
    return (
      <div className="surface p-5">
        <Alert tone="error" title="We couldn't load this dashboard.">
          Please try again in a moment. Your financial and operational data will refresh automatically.
        </Alert>
      </div>
    );
  }
  const data = dashboard.data?.data || {};
  const appRows = listData(applications.data);
  const claimRows = listData(claims.data);
  const inspectionRows = listData(inspections.data);

  return (
    <div>
      <DashboardHero
        image="/images/hero-insurer.svg"
        alt="Corporate insurance environment"
        eyebrow="Provider operations"
        title="Manage your insurance business."
        text="Products, quote requests, applications, claims and collections across your organization."
        actions={
          <>
            <Link to="/provider/quotes"><Button variant="secondary" icon={FileSearch}>Quote requests</Button></Link>
            <Link to="/provider/products"><Button icon={Package}>Manage products</Button></Link>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Package} label="Active products" value={data.active_products ?? 0} hint={`${data.products ?? 0} total products`} />
        <Stat icon={ClipboardList} label="Applications pending" value={data.applications_pending ?? 0} hint={`${data.applications_received ?? 0} received`} tone="amber" />
        <Stat icon={ShieldCheck} label="Active policies" value={data.active_policies ?? 0} hint={`${data.policies_expiring_soon ?? 0} expiring soon`} tone="ink" />
        <Stat icon={Wallet} label="Premium collected" value={formatCurrency(data.premium_collected)} hint={`${data.payments_awaiting_verification ?? 0} awaiting verification`} tone="lime" />
      </div>

      <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-ink-100 bg-white p-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-bold text-ink-900">Financial period</p>
          <p className="mt-1 text-xs text-ink-500">Filter premium, commission and settlement figures by date.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <Input label="From" type="date" value={period.start} max={period.end || undefined} onChange={(event) => setPeriod((current) => ({ ...current, start: event.target.value }))} />
          <Input label="To" type="date" value={period.end} min={period.start || undefined} onChange={(event) => setPeriod((current) => ({ ...current, end: event.target.value }))} />
          <Button variant="secondary" size="sm" disabled={!period.start && !period.end} onClick={() => setPeriod({ start: "", end: "" })}>Clear</Button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Wallet} label="Net premium collected" value={formatCurrency(financial.data?.net_premium_collected)} hint="After completed refunds" tone="lime" />
        <Stat icon={ShieldCheck} label="Premium earned" value={formatCurrency(financial.data?.premium_earned_recognized)} hint="Recognized on policy issuance" tone="ink" />
        <Stat icon={ClipboardList} label="Commissions outstanding" value={formatCurrency(financial.data?.commissions_outstanding)} hint="Pending, approved or payable" tone="amber" />
        <Stat icon={CalendarCheck} label="Outstanding settlements" value={formatCurrency(financial.data?.outstanding_settlements)} hint="Pending insurer settlement" tone="blue" />
      </div>

      {data.claims_requiring_action > 0 && (
        <div className="mt-5 flex flex-col justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-100 text-amber-700"><TriangleAlert className="h-4 w-4" /></span>
            <div>
              <p className="text-sm font-bold text-amber-900">{data.claims_requiring_action} claims need action</p>
              <p className="text-xs text-amber-700">Review, request information or schedule an inspection.</p>
            </div>
          </div>
          <Link to="/claims"><Button size="sm" variant="secondary">Open claims workspace <ArrowRight className="h-3.5 w-3.5" /></Button></Link>
        </div>
      )}

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div>
          <SectionTitle
            title="Latest applications"
            description="New business arriving from the marketplace."
            action={<Link to="/provider/applications" className="text-xs font-bold text-brand-700 hover:underline">View all</Link>}
          />
          <div className="surface overflow-hidden">
            {appRows.length ? (
              <div className="divide-y divide-ink-100">
                {appRows.map((app) => (
                  <Link key={app.id} to="/provider/applications" className="flex flex-col gap-2 p-4 transition hover:bg-ink-50/60 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-bold text-ink-900">{app.application_number}</p>
                      <p className="mt-0.5 text-xs text-ink-500">{app.customer_name} · {app.vehicle_summary?.registration_number}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <p className="text-sm font-semibold text-ink-900">{formatCurrency(app.premium)}</p>
                      <StatusBadge status={app.status} />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="p-6 text-sm text-ink-500">No applications yet. Publish active products to receive marketplace requests.</p>
            )}
          </div>

          <div className="mt-7 grid gap-4 sm:grid-cols-2">
            <Link to="/provider/quotes" className="surface group p-5 transition hover:-translate-y-0.5 hover:border-brand-200">
              <FileSearch className="h-6 w-6 text-brand-600" />
              <p className="mt-4 font-display text-base font-bold text-ink-950">Open quote requests</p>
              <p className="mt-1 text-2xl font-bold text-ink-950">{data.open_quotation_requests ?? 0}</p>
              <p className="mt-1 text-xs text-ink-400">Respond with a product-based quote.</p>
            </Link>
            <Link to="/provider/payments" className="surface group p-5 transition hover:-translate-y-0.5 hover:border-brand-200">
              <Wallet className="h-6 w-6 text-brand-600" />
              <p className="mt-4 font-display text-base font-bold text-ink-950">Pending verification</p>
              <p className="mt-1 text-2xl font-bold text-ink-950">{data.payments_awaiting_verification ?? 0}</p>
              <p className="mt-1 text-xs text-ink-400">Reconcile against provider references.</p>
            </Link>
          </div>
        </div>

        <div>
          <SectionTitle title="Claims requiring action" action={<Link to="/claims" className="text-xs font-bold text-brand-700 hover:underline">Open queue</Link>} />
          <div className="surface divide-y divide-ink-100">
            {claimRows.length ? claimRows.map((claim) => (
              <Link key={claim.id} to={`/claims/${claim.id}`} className="block p-4 transition hover:bg-ink-50/60">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold text-ink-900">{claim.claim_number}</p>
                  <StatusBadge status={claim.status} />
                </div>
                <p className="mt-1 text-xs text-ink-500">{titleize(claim.claim_type)} · {formatCurrency(claim.amount_claimed)}</p>
              </Link>
            )) : <p className="p-5 text-sm text-ink-500">No active claims.</p>}
          </div>

          <SectionTitle title="Inspections" className="mt-7" action={<Link to="/inspections" className="text-xs font-bold text-brand-700 hover:underline">View all</Link>} />
          <div className="surface divide-y divide-ink-100">
            {inspectionRows.length ? inspectionRows.map((inspection) => (
              <Link key={inspection.id} to={`/inspections/${inspection.id}`} className="block p-4 transition hover:bg-ink-50/60">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold text-ink-900">{inspection.inspection_number}</p>
                  <StatusBadge status={inspection.status} />
                </div>
                <p className="mt-1 text-xs text-ink-500">{inspection.vehicle_summary?.registration_number} · {inspection.inspector_name || "Unassigned"}</p>
                <p className="mt-1 text-[10px] text-ink-400">{formatDateTime(inspection.scheduled_at)}</p>
              </Link>
            )) : <p className="p-5 text-sm text-ink-500">No inspections scheduled.</p>}
          </div>

          <div className="mt-6 rounded-3xl bg-ink-950 p-5 text-white">
            <CalendarCheck className="h-6 w-6 text-lime-300" />
            <p className="mt-4 font-display text-lg font-bold">{data.inspections_scheduled ?? 0} inspections scheduled</p>
            <p className="mt-1 text-xs leading-relaxed text-white/50">Inspectors record damage against 20 standardized vehicle zones, including a 3D visual record.</p>
            <Link to="/inspections" className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-lime-300">Manage inspections <ArrowRight className="h-3.5 w-3.5" /></Link>
          </div>
        </div>
      </div>
    </div>
  );
}
