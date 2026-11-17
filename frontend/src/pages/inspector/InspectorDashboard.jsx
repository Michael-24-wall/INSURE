import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, CalendarCheck, CheckCircle2, ClipboardCheck, MapPin, Timer } from "lucide-react";
import api, { listData } from "../../api/client";
import { formatDateTime } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, Button, PageLoader, SectionTitle, Stat, StatusBadge } from "../../components/ui";

export default function InspectorDashboard() {
  const dashboard = useQuery({
    queryKey: ["dashboard", "inspector"],
    queryFn: async () => (await api.get("/analytics/dashboard/")).data,
  });
  const inspections = useQuery({
    queryKey: ["inspections", "inspector-dashboard"],
    queryFn: async () => (await api.get("/inspections/?page_size=50&ordering=scheduled_at")).data,
  });

  if (dashboard.isLoading) return <PageLoader />;
  if (dashboard.isError) {
    return <div className="surface p-5"><Alert title="We couldn't load your dashboard">Please check your connection and try again.</Alert></div>;
  }
  const data = dashboard.data?.data || {};
  const rows = listData(inspections.data);
  const active = rows.filter((item) => ["scheduled", "in_progress"].includes(item.status));

  return (
    <div>
      <DashboardHero
        image="/images/hero-inspection.svg"
        alt="Vehicle inspection environment"
        eyebrow="Inspector workspace"
        title="Accurate inspections. Better protection."
        text="Open assigned jobs, capture zonal damage and complete structured reports."
        actions={<Link to="/inspector/inspections"><Button icon={CalendarCheck}>All inspections</Button></Link>}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={ClipboardCheck} label="Assigned" value={data.assigned ?? 0} hint="All time" />
        <Stat icon={Timer} label="Active" value={data.scheduled ?? 0} hint="Scheduled or in progress" tone="amber" />
        <Stat icon={CheckCircle2} label="Completed" value={data.completed ?? 0} hint="Reports submitted" tone="lime" />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div>
          <SectionTitle title="Active jobs" description="Jobs that need your attention." />
          <div className="space-y-3">
            {inspections.isError ? (
              <div className="surface p-5"><Alert>Couldn&apos;t load your inspections. Please try again.</Alert></div>
            ) : active.length ? active.map((inspection) => (
              <Link key={inspection.id} to={`/inspector/inspections/${inspection.id}`} className="surface flex flex-col gap-4 p-5 transition hover:-translate-y-0.5 hover:border-brand-200 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700"><CalendarCheck className="h-5 w-5" /></span>
                  <div>
                    <p className="text-sm font-bold text-ink-950">{inspection.inspection_number}</p>
                    <p className="mt-0.5 text-xs text-ink-500">{inspection.vehicle_summary?.registration_number} · {inspection.vehicle_summary?.make} {inspection.vehicle_summary?.model}</p>
                    <p className="mt-1 flex items-center gap-1 text-[11px] text-ink-400"><MapPin className="h-3 w-3" /> {inspection.location || "Location not set"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-[10px] text-ink-400">Scheduled</p>
                    <p className="text-xs font-semibold text-ink-800">{formatDateTime(inspection.scheduled_at)}</p>
                  </div>
                  <StatusBadge status={inspection.status} />
                  <ArrowRight className="h-4 w-4 text-ink-300" />
                </div>
              </Link>
            )) : (
              <div className="surface p-8 text-center">
                <CheckCircle2 className="mx-auto h-7 w-7 text-brand-500" />
                <p className="mt-3 text-sm font-bold text-ink-900">You’re all caught up</p>
                <p className="mt-1 text-xs text-ink-400">New inspection assignments will appear here.</p>
              </div>
            )}
          </div>
        </div>

        <div>
          <SectionTitle title="Upcoming schedule" />
          <div className="surface divide-y divide-ink-100">
            {(data.upcoming || []).length ? data.upcoming.map((item) => (
              <div key={item.id} className="p-4">
                <p className="text-xs font-bold text-ink-900">{item.inspection_number}</p>
                <p className="mt-1 text-xs text-ink-500">{item.vehicle__registration_number}</p>
                <p className="mt-1 text-[10px] text-ink-400">{formatDateTime(item.scheduled_at)} · {item.location}</p>
              </div>
            )) : <p className="p-5 text-sm text-ink-500">No upcoming inspections.</p>}
          </div>

          <div className="mt-6 rounded-3xl bg-gradient-to-br from-brand-700 to-ink-950 p-5 text-white">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-lime-300">Field tip</p>
            <p className="mt-3 font-display text-lg font-bold">Capture evidence as you go.</p>
            <p className="mt-2 text-xs leading-relaxed text-white/55">Add a photo and repair estimate to each damage record. Complete assessments make claims faster and fairer.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
