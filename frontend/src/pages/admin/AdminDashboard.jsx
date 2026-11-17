import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, Building2, ShieldCheck, TriangleAlert, Users, Wallet } from "lucide-react";
import api, { listData } from "../../api/client";
import { compactCurrency, formatCurrency, formatDate, titleize } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, PageLoader, SectionTitle, Stat, StatusBadge } from "../../components/ui";

const COLORS = ["#0d946b", "#10b981", "#34d399", "#6ee7bb", "#a7f3d5", "#d1fae9", "#94a3b8", "#64748b"];

export default function AdminDashboard() {
  const dashboard = useQuery({
    queryKey: ["dashboard", "admin"],
    queryFn: async () => (await api.get("/admin/dashboard/")).data,
  });
  const audit = useQuery({
    queryKey: ["audit", "dashboard"],
    queryFn: async () => (await api.get("/admin/audit-logs/?limit=7")).data,
  });
  const organizations = useQuery({
    queryKey: ["organizations", "pending"],
    queryFn: async () => (await api.get("/organizations/?status=pending&page_size=5")).data,
  });

  if (dashboard.isLoading || audit.isLoading || organizations.isLoading) return <PageLoader />;
  if (dashboard.isError || audit.isError || organizations.isError) {
    return (
      <div className="surface p-5">
        <Alert title="We couldn't load the platform dashboard.">
          Refresh the page to retry. Operational data has not been changed.
        </Alert>
      </div>
    );
  }
  const data = dashboard.data || {};
  const revenue = (data.revenue_by_month || []).map((row) => ({
    month: row.month ? new Date(row.month).toLocaleDateString("en", { month: "short" }) : "—",
    total: Number(row.total),
    count: row.count,
  }));
  const policyStatus = (data.policies_by_status || []).map((row) => ({ name: titleize(row.status), value: row.count }));
  const pendingOrgs = listData(organizations.data);
  const logs = Array.isArray(audit.data) ? audit.data : listData(audit.data);

  return (
    <div>
      <DashboardHero
        image="/images/hero-network.svg"
        alt="Connected insurance platform"
        eyebrow="Platform control"
        title="Your InsureConnect control centre."
        text="Users, providers, dealerships, policies, claims and financial activity across InsureConnect."
      />

      {data.organizations?.pending > 0 && (
        <Link to="/admin/organizations" className="mb-5 flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 transition hover:border-amber-300">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-100 text-amber-700"><Building2 className="h-4 w-4" /></span>
            <div>
              <p className="text-sm font-bold text-amber-900">{data.organizations.pending} organizations awaiting verification</p>
              <p className="text-xs text-amber-700">Review submitted provider details to activate marketplace access.</p>
            </div>
          </div>
          <ArrowRight className="h-4 w-4 text-amber-700" />
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Users} label="Total users" value={data.users?.total ?? 0} hint={`${data.users?.customers ?? 0} customers`} />
        <Stat icon={ShieldCheck} label="Policies" value={data.marketplace?.policies ?? 0} hint={`${data.marketplace?.active_policies ?? 0} active`} tone="ink" />
        <Stat icon={Wallet} label="Gross collected" value={formatCurrency(data.finance?.gross_collected)} hint={`${formatCurrency(data.finance?.collected_this_month)} this month`} tone="lime" />
        <Stat icon={TriangleAlert} label="Open claims" value={data.claims?.open ?? 0} hint={`${data.claims?.pending_review ?? 0} pending review`} tone="amber" />
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="surface p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Organizations</p>
          <div className="mt-2 flex items-end justify-between">
            <p className="font-display text-2xl font-bold text-ink-950">{data.organizations?.verified ?? 0}</p>
            <p className="text-[11px] text-ink-400">{data.organizations?.pending ?? 0} pending</p>
          </div>
        </div>
        <div className="surface p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Products live</p>
          <div className="mt-2 flex items-end justify-between">
            <p className="font-display text-2xl font-bold text-ink-950">{data.catalogue?.active_products ?? 0}</p>
            <p className="text-[11px] text-ink-400">{data.catalogue?.insurers ?? 0} insurers</p>
          </div>
        </div>
        <div className="surface p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Applications</p>
          <div className="mt-2 flex items-end justify-between">
            <p className="font-display text-2xl font-bold text-ink-950">{data.marketplace?.applications ?? 0}</p>
            <p className="text-[11px] text-ink-400">{data.marketplace?.applications_pending ?? 0} pending</p>
          </div>
        </div>
        <div className="surface p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Inspections</p>
          <div className="mt-2 flex items-end justify-between">
            <p className="font-display text-2xl font-bold text-ink-950">{data.inspections?.completed ?? 0}</p>
            <p className="text-[11px] text-ink-400">{data.inspections?.scheduled ?? 0} active</p>
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="surface p-5">
          <SectionTitle title="Collected premium" description="Verified payment volume by month." />
          <div className="h-[260px]">
            {revenue.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={revenue} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                  <defs>
                    <linearGradient id="revenue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0d946b" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#0d946b" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e7ecef" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#7894a4" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#7894a4" }} axisLine={false} tickLine={false} tickFormatter={(value) => compactCurrency(value)} />
                  <Tooltip formatter={(value) => formatCurrency(value)} contentStyle={{ borderRadius: 12, border: "1px solid #e7ecef", fontSize: 12 }} />
                  <Area type="monotone" dataKey="total" stroke="#0d946b" strokeWidth={2.5} fill="url(#revenue)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-ink-400">No verified payments yet.</div>
            )}
          </div>
        </div>

        <div className="surface p-5">
          <SectionTitle title="Policies by status" />
          <div className="h-[260px]">
            {policyStatus.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={policyStatus} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90} paddingAngle={3}>
                    {policyStatus.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e7ecef", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-ink-400">No policies issued yet.</div>
            )}
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-3 text-[10px] text-ink-500">
            {policyStatus.map((entry, index) => (
              <span key={entry.name} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: COLORS[index % COLORS.length] }} /> {entry.name} ({entry.value})
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <div>
          <SectionTitle title="Provider performance" description="Quotation activity across the marketplace." />
          <div className="surface overflow-hidden">
            {(data.provider_performance || []).length ? (
              <div className="divide-y divide-ink-100">
                {data.provider_performance.map((row, index) => (
                  <div key={row.insurer} className="flex items-center justify-between gap-4 p-4">
                    <div className="flex items-center gap-3">
                      <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink-100 text-[11px] font-bold text-ink-600">{index + 1}</span>
                      <div>
                        <p className="text-xs font-bold text-ink-900">{row.insurer}</p>
                        <p className="text-[10px] text-ink-400">{row.quotations} quotations</p>
                      </div>
                    </div>
                    <p className="text-xs font-bold text-ink-900">{formatCurrency(row.premium)}</p>
                  </div>
                ))}
              </div>
            ) : <p className="p-5 text-sm text-ink-500">No quotation activity.</p>}
          </div>

          <SectionTitle title="Claims by status" className="mt-7" />
          <div className="surface p-5">
            <div className="h-[200px]">
              {(data.claims_by_status || []).length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={(data.claims_by_status || []).map((row) => ({ name: titleize(row.status), count: row.count }))} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e7ecef" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#7894a4" }} axisLine={false} tickLine={false} interval={0} angle={-18} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10, fill: "#7894a4" }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e7ecef", fontSize: 12 }} />
                    <Bar dataKey="count" fill="#0d946b" radius={[6, 6, 0, 0]} maxBarSize={38} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="flex h-full items-center justify-center text-sm text-ink-400">No claims recorded.</div>}
            </div>
          </div>
        </div>

        <div>
          <SectionTitle title="Verification queue" action={<Link to="/admin/organizations" className="text-xs font-bold text-brand-700 hover:underline">Review all</Link>} />
          <div className="surface divide-y divide-ink-100">
            {pendingOrgs.length ? pendingOrgs.map((org) => (
              <div key={org.id} className="flex items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-xs font-bold text-ink-900">{org.name}</p>
                  <p className="mt-0.5 text-[10px] text-ink-400">{titleize(org.organization_type)} · {formatDate(org.created_at)}</p>
                </div>
                <StatusBadge status={org.status} />
              </div>
            )) : <p className="p-5 text-sm text-ink-500">No organizations waiting.</p>}
          </div>

          <SectionTitle title="Recent audit activity" className="mt-7" action={<Link to="/admin/audit" className="text-xs font-bold text-brand-700 hover:underline">Full log</Link>} />
          <div className="surface divide-y divide-ink-100">
            {logs.length ? logs.map((log) => (
              <div key={log.id} className="p-4">
                <p className="text-[11px] font-semibold text-ink-800">{titleize(log.action)}</p>
                <p className="mt-0.5 truncate text-[10px] text-ink-400">{log.actor || "system"} · {log.entity_type || "—"}</p>
                <p className="mt-1 text-[10px] text-ink-300">{formatDate(log.created_at)}</p>
              </div>
            )) : <p className="p-5 text-sm text-ink-500">No activity recorded.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
