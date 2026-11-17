import { Link } from "react-router-dom";
import { ArrowLeft, BadgeCheck, Check, ShieldCheck } from "lucide-react";
import { Brand } from "../../components/Brand";

export default function AuthLayout({ children, eyebrow, title, description }) {
  return (
    <div className="min-h-screen bg-sand-50 lg:grid lg:grid-cols-[0.95fr_1.05fr]">
      <aside className="relative hidden overflow-hidden bg-ink-950 p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="landing-grid absolute inset-0 opacity-50" />
        <div className="absolute -bottom-32 -right-24 h-[400px] w-[400px] rounded-full bg-brand-500/20 blur-[110px]" />
        <div className="relative">
          <Brand light />
          <div className="mt-24 max-w-md">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-lime-200">
              <ShieldCheck className="h-3.5 w-3.5" /> All insurance. One connected ecosystem.
            </span>
            <h2 className="mt-6 font-display text-4xl font-bold leading-tight tracking-tight">Every protection journey in one clear view.</h2>
            <p className="mt-4 text-sm leading-relaxed text-white/50">A connected workspace for customers, insurers, brokers, agents, partners and claims teams.</p>
            <div className="mt-9 space-y-4">
              {["Connected provider marketplace", "Structured claims workflow", "Role-based operations", "Auditable payment reconciliation"].map((item) => (
                <div key={item} className="flex items-center gap-3 text-sm text-white/70">
                  <span className="grid h-6 w-6 place-items-center rounded-full bg-lime-300/15 text-lime-300"><Check className="h-3.5 w-3.5" /></span>
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="relative rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-lime-300 text-ink-950"><BadgeCheck className="h-5 w-5" /></span>
            <div>
              <p className="text-sm font-bold">Provider-grade controls</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-white/45">Organization isolation, role permissions and a complete audit trail.</p>
            </div>
          </div>
        </div>
      </aside>

      <main className="flex min-h-screen flex-col">
        <div className="flex items-center justify-between p-5 sm:px-8 lg:justify-end">
          <div className="lg:hidden"><Brand /></div>
          <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to home
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center px-5 pb-12 pt-4 sm:px-8">
          <div className="w-full max-w-[440px] animate-fade-up">
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink-950">{title}</h1>
            {description && <p className="mt-2 text-sm leading-relaxed text-ink-500">{description}</p>}
            <div className="mt-7">{children}</div>
          </div>
        </div>
      </main>
    </div>
  );
}
