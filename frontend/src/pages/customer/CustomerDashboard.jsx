import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Car,
  FileSearch,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import api, { listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { formatCurrency, formatDate, titleize } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, Button, PageLoader, SectionTitle, Stat, StatusBadge } from "../../components/ui";

export default function CustomerDashboard() {
  const { user } = useAuth();
  const dashboard = useQuery({
    queryKey: ["dashboard", "customer"],
    queryFn: async () => (await api.get("/analytics/dashboard/")).data,
  });
  const policies = useQuery({
    queryKey: ["policies", "dashboard"],
    queryFn: async () => (await api.get("/policies/?page_size=5&ordering=-created_at")).data,
  });
  const claims = useQuery({
    queryKey: ["claims", "dashboard"],
    queryFn: async () => (await api.get("/claims/?page_size=5&ordering=-created_at")).data,
  });
  const applications = useQuery({
    queryKey: ["applications", "dashboard"],
    queryFn: async () => (await api.get("/applications/?page_size=20&ordering=-created_at")).data,
  });

  if (dashboard.isLoading || policies.isLoading || claims.isLoading || applications.isLoading) return <PageLoader />;
  if (dashboard.isError || policies.isError || claims.isError || applications.isError) {
    return (
      <div className="surface p-5">
        <Alert title="We couldn't load your dashboard.">
          Please check your connection and try again. Your policies, claims and payments remain unchanged.
        </Alert>
      </div>
    );
  }
  const data = dashboard.data?.data || {};
  const policyRows = listData(policies.data);
  const claimRows = listData(claims.data);
  const payable = listData(applications.data).filter((app) => app.status === "approved");

  return (
    <div>
      <DashboardHero
        image="/images/hero-marketplace.svg"
        alt="Vehicles in a lineup"
        eyebrow={`Welcome back, ${user?.first_name || "there"}`}
        title="Your protection, all in one place."
        text={data.active_policies ? `${data.active_policies} active ${data.active_policies === 1 ? "policy" : "policies"} keeping you moving.` : "Your first policy starts with a single quote."}
        actions={<Link to="/app/marketplace"><Button>Get a new quote</Button></Link>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={ShieldCheck} label="Active policies" value={data.active_policies ?? 0} hint={`${data.policies_expiring_soon ?? 0} expiring soon`} />
        <Stat icon={Car} label="Registered vehicles" value={data.vehicles ?? 0} hint="Ready for quotes" tone="ink" />
        <Stat icon={TriangleAlert} label="Open claims" value={data.open_claims ?? 0} hint="Being processed" tone="amber" />
        <Stat icon={Wallet} label="Total paid" value={formatCurrency(data.total_paid)} hint="Successful payments" tone="lime" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div>
          <SectionTitle
            title="Your policies"
            description="Cover currently or recently in force."
            action={<Link to="/app/policies" className="text-xs font-bold text-brand-700 hover:underline">View all</Link>}
          />
          {policyRows.length ? (
            <div className="space-y-3">
              {policyRows.map((policy) => (
                <div key={policy.id} className="surface flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-700"><ShieldCheck className="h-5 w-5" /></span>
                    <div>
                      <p className="text-sm font-bold text-ink-950">{policy.policy_number}</p>
                      <p className="text-xs text-ink-400">{policy.vehicle_summary?.registration_number} · {policy.product_name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-5 text-xs">
                    <div>
                      <p className="text-ink-400">Premium</p>
                      <p className="font-bold text-ink-900">{formatCurrency(policy.premium)}</p>
                    </div>
                    <div>
                      <p className="text-ink-400">Expires</p>
                      <p className="font-semibold text-ink-900">{formatDate(policy.end_date)}</p>
                    </div>
                    <StatusBadge status={policy.status} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="surface flex flex-col items-start gap-3 p-6">
              <p className="text-sm font-semibold text-ink-900">No policy yet</p>
              <p className="text-sm text-ink-500">Add a vehicle and request your first quotation. It takes less than two minutes.</p>
              <Link to="/app/marketplace"><Button size="sm" icon={FileSearch}>Start a quotation</Button></Link>
            </div>
          )}

          {payable.length > 0 && (
            <div className="mt-7">
              <SectionTitle title="Complete your payment" description="These applications are open for premium payment." />
              <div className="space-y-3">
                {payable.slice(0, 3).map((app) => (
                  <Link key={app.id} to={`/app/applications/${app.id}`} className="block rounded-2xl border border-amber-200 bg-amber-50 p-4 transition hover:border-amber-300">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-ink-900">{app.application_number}</p>
                        <p className="text-xs text-ink-500">{app.insurer_name} · {formatCurrency(app.premium)}</p>
                      </div>
                      <StatusBadge status={app.status} />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <SectionTitle title="Recent claims" action={<Link to="/app/claims" className="text-xs font-bold text-brand-700 hover:underline">View all</Link>} />
          <div className="surface overflow-hidden">
            {claimRows.length ? (
              <div className="divide-y divide-ink-100">
                {claimRows.map((claim) => (
                  <Link key={claim.id} to={`/app/claims/${claim.id}`} className="block p-4 transition hover:bg-ink-50/60">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-bold text-ink-900">{claim.claim_number}</p>
                      <StatusBadge status={claim.status} />
                    </div>
                    <p className="mt-1 text-xs text-ink-500">{titleize(claim.claim_type)} · {formatCurrency(claim.amount_claimed)}</p>
                    <p className="mt-1 text-[10px] text-ink-400">{formatDate(claim.created_at)}</p>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center">
                <TriangleAlert className="mx-auto h-6 w-6 text-ink-300" />
                <p className="mt-2 text-sm font-semibold text-ink-800">No claims filed</p>
                <p className="mt-1 text-xs text-ink-400">If something happens, your policy is just a click away.</p>
              </div>
            )}
          </div>

          <div className="mt-6 rounded-3xl bg-gradient-to-br from-brand-600 to-brand-800 p-5 text-white">
            <Sparkles className="h-6 w-6 text-lime-300" />
            <p className="mt-4 font-display text-lg font-bold">Not sure what cover you need?</p>
            <p className="mt-1.5 text-xs leading-relaxed text-white/60">Use the insurance assistant to understand comprehensive, third-party and commercial cover before you buy.</p>
            <Link to="/app/marketplace" className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-lime-300">Explore cover <ArrowRight className="h-3.5 w-3.5" /></Link>
          </div>
        </div>
      </div>
    </div>
  );
}
