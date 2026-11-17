import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  Building2,
  Check,
  HeartPulse,
  Home,
  LifeBuoy,
  Network,
  Plane,
  Ship,
  ShieldCheck,
  Sparkles,
  Store,
  Users,
  Wallet,
} from "lucide-react";
import { Brand } from "../../components/Brand";
import { Button } from "../../components/ui";
import { INSURANCE_LINES } from "../../lib/constants";

const lineIcons = {
  motor: Store,
  health: HeartPulse,
  life: LifeBuoy,
  business: Building2,
  property: Home,
  travel: Plane,
  marine: Ship,
  agriculture: Sparkles,
  accident: ShieldCheck,
  liability: BadgeCheck,
};

const participants = [
  ["Customers", "Discover cover, compare options and manage every policy and claim.", Users],
  ["Insurance companies", "Publish products, underwrite risk and serve customers through one workflow.", ShieldCheck],
  ["Brokers and agents", "Bring advice, distribution and relationship management into the ecosystem.", Network],
  ["Dealerships", "Connect vehicle customers to trusted insurers without leaving the sales journey.", Store],
  ["Corporate organisations", "Coordinate employee, asset and operational protection at scale.", Building2],
  ["Partners and inspectors", "Contribute verified services, evidence and specialist expertise.", BadgeCheck],
  ["Platform administrators", "Govern access, organisations, compliance, audit and marketplace trust.", Wallet],
];

const capabilities = [
  ["Discover and compare", "Structured product discovery and quote requests, starting with live motor products and expanding by line."],
  ["Connect every participant", "Tenant-aware workspaces for customers, insurers, brokers, agents, dealerships, corporations and partners."],
  ["Operate with confidence", "Applications, policies, payments, claims, commissions, notifications and audit trails in one connected system."],
  ["Extend without re-platforming", "A product-based architecture lets providers add new insurance lines as the corresponding workflows become operational."],
];

export default function Landing() {
  return (
    <div className="bg-sand-50">
      <header className="sticky top-0 z-50 border-b border-ink-100/70 bg-sand-50/90 backdrop-blur-xl">
        <div className="mx-auto flex h-[74px] max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Brand />
          <nav className="hidden items-center gap-7 text-sm font-semibold text-ink-500 md:flex">
            <a href="#platform" className="hover:text-ink-950">Platform</a>
            <a href="#lines" className="hover:text-ink-950">Insurance lines</a>
            <a href="#ecosystem" className="hover:text-ink-950">Ecosystem</a>
            <a href="#providers" className="hover:text-ink-950">For providers</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="hidden rounded-xl px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-ink-100 sm:block">Sign in</Link>
            <Link to="/register"><Button size="sm" className="h-10">Join the ecosystem <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </header>

      <section className="relative isolate overflow-hidden bg-ink-950 text-white">
        <div className="landing-grid absolute inset-0 opacity-30" />
        <div className="absolute -right-32 -top-32 h-[520px] w-[520px] rounded-full bg-brand-500/25 blur-[100px]" />
        <div className="relative mx-auto grid min-h-[620px] max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:px-8 lg:py-24">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-brand-200">
              All insurance. One connected ecosystem.
            </p>
            <h1 className="mt-6 max-w-3xl font-display text-5xl font-bold leading-[1.02] tracking-[-0.04em] sm:text-6xl lg:text-7xl">
              Insurance for every part of life and business.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-white/65">
              INSURECONNECT connects people, providers and partners across the insurance value chain — from discovery and advice to claims, settlement and renewal.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link to="/register"><Button variant="accent" size="lg">Explore insurance <ArrowRight className="h-4 w-4" /></Button></Link>
              <Link to="/register?type=provider"><Button variant="dark" size="lg">Connect your organisation</Button></Link>
            </div>
            <div className="mt-9 flex flex-wrap gap-x-6 gap-y-3 text-xs text-white/60">
              {["Verified providers", "Permissioned workspaces", "Evidence-led operations"].map((item) => (
                <span key={item} className="flex items-center gap-1.5"><Check className="h-4 w-4 text-brand-300" /> {item}</span>
              ))}
            </div>
          </div>
          <div className="relative grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              ["People", Users, "bg-brand-500/25"],
              ["Health", HeartPulse, "bg-rose-400/20"],
              ["Business", Building2, "bg-accent-500/20"],
              ["Property", Home, "bg-sky-400/20"],
              ["Travel", Plane, "bg-lime-300/15"],
              ["Cargo", Ship, "bg-violet-400/20"],
            ].map(([label, Icon, tone], index) => (
              <div key={label} className={`rounded-3xl border border-white/10 ${tone} p-5 backdrop-blur ${index % 2 ? "mt-6" : ""}`}>
                <Icon className="h-7 w-7 text-white" />
                <p className="mt-10 text-sm font-bold">{label}</p>
                <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-white/40">Connected</p>
              </div>
            ))}
            <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 rounded-2xl border border-white/15 bg-white px-4 py-3 text-xs font-bold text-ink-950 shadow-xl">
              One connected operating system
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-ink-100 bg-ink-950">
        <div className="mx-auto grid max-w-7xl grid-cols-2 divide-x divide-white/10 px-4 sm:px-6 md:grid-cols-4 lg:px-8">
          {[["10", "insurance lines mapped"], ["1", "connected ecosystem"], ["24/7", "digital access"], ["100%", "auditable workflows"]].map(([value, label]) => (
            <div key={label} className="px-4 py-6 text-center sm:py-8">
              <p className="font-display text-2xl font-bold text-brand-300 sm:text-3xl">{value}</p>
              <p className="mt-1 text-[11px] text-white/45">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="lines" className="bg-white">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
          <div className="max-w-3xl">
            <p className="eyebrow">Insurance lines</p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink-950 sm:text-4xl">A marketplace designed for the whole industry.</h2>
            <p className="mt-4 text-base leading-relaxed text-ink-500">
              Browse the lines INSURECONNECT is designed to support. Motor products are operational today; other lines are clearly marked until providers and workflows are enabled — no invented quotes, policies or payment confirmations.
            </p>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {INSURANCE_LINES.map((line) => {
              const Icon = lineIcons[line.value];
              return (
                <div key={line.value} className={`rounded-3xl border p-5 ${line.status === "live" ? "border-brand-200 bg-brand-50/60" : "border-ink-100 bg-white"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="grid h-10 w-10 place-items-center rounded-2xl bg-white text-brand-700 shadow-sm"><Icon className="h-5 w-5" /></span>
                    <span className={`rounded-full px-2 py-1 text-[9px] font-bold uppercase tracking-wide ${line.status === "live" ? "bg-brand-700 text-white" : "bg-ink-100 text-ink-500"}`}>
                      {line.status === "live" ? "Live" : "Expanding"}
                    </span>
                  </div>
                  <h3 className="mt-5 font-display text-base font-bold text-ink-950">{line.label}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-ink-500">{line.description}</p>
                </div>
              );
            })}
          </div>
          <p className="mt-6 text-xs text-ink-400">Product availability is determined by verified providers publishing products through the platform.</p>
        </div>
      </section>

      <section id="platform" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
        <div className="max-w-3xl">
          <p className="eyebrow">The connected platform</p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink-950 sm:text-4xl">One connected operating system for insurance.</h2>
          <p className="mt-4 text-base leading-relaxed text-ink-500">The infrastructure layer connecting products, people and processes without forcing every insurance line into the same customer journey.</p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {capabilities.map(([title, text], index) => (
            <div key={title} className="rounded-3xl border border-ink-100 bg-white p-6 shadow-card">
              <span className="grid h-10 w-10 place-items-center rounded-2xl bg-brand-50 font-display text-sm font-bold text-brand-700">0{index + 1}</span>
              <h3 className="mt-5 font-display text-base font-bold text-ink-950">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-500">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="ecosystem" className="border-y border-ink-100 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="eyebrow">The ecosystem</p>
              <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink-950 sm:text-4xl">Every participant has a place at the table.</h2>
              <p className="mt-4 text-base leading-relaxed text-ink-500">INSURECONNECT gives each participant the right tools, permissions and visibility while keeping the network connected.</p>
              <Link to="/register" className="mt-8 inline-flex items-center gap-2 text-sm font-bold text-brand-700 hover:underline">Join the ecosystem <ArrowRight className="h-4 w-4" /></Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {participants.map(([title, text, Icon]) => (
                <div key={title} className="rounded-3xl border border-ink-100 bg-ink-50/60 p-5">
                  <Icon className="h-5 w-5 text-brand-700" />
                  <h3 className="mt-4 font-display text-sm font-bold text-ink-950">{title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-ink-500">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="providers" className="bg-ink-950 text-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:items-center lg:px-8 lg:py-24">
          <div>
            <p className="eyebrow !text-accent-300">For insurers, brokers, agents and partners</p>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight sm:text-4xl">Manage your entire insurance portfolio in one place.</h2>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-white/55">Publish products, respond to structured requests, review applications, verify payments, coordinate services and manage claims with role-based teams.</p>
            <div className="mt-7 grid gap-3 sm:grid-cols-2">
              {["Organisation-scoped access", "Product and commission management", "Integrations and webhook logs", "Complete audit trail"].map((item) => (
                <div key={item} className="flex items-center gap-2 text-sm text-white/70"><Check className="h-4 w-4 text-accent-300" /> {item}</div>
              ))}
            </div>
            <Link to="/register?type=provider" className="mt-8 inline-flex"><Button variant="accent">Connect your business <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
            <div className="flex items-center gap-3 border-b border-white/10 pb-5">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-accent-500 text-white"><Network className="h-5 w-5" /></span>
              <div><p className="font-display font-bold">Connected operations</p><p className="text-xs text-white/45">One source of truth across your network</p></div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              {[["Products", "Publish and govern"], ["Quotes", "Respond and compare"], ["Policies", "Issue and renew"], ["Claims", "Track and settle"]].map(([title, text]) => (
                <div key={title} className="rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-sm font-bold">{title}</p><p className="mt-1 text-[11px] text-white/45">{text}</p></div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="grain relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-brand-600 to-brand-900 px-6 py-12 text-white sm:px-12 sm:py-16">
          <div className="relative z-10 flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
            <div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/60">The future of insurance is connected</p><h2 className="mt-3 max-w-xl font-display text-3xl font-bold tracking-tight sm:text-4xl">All insurance. One connected ecosystem.</h2></div>
            <Link to="/register"><Button variant="accent" size="lg">Get started <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-200/60 bg-sand-50">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1.3fr_1fr_1fr] lg:px-8">
          <div>
            <Brand />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-500">All insurance, one connected ecosystem for customers, providers and the partners who make protection possible.</p>
            <p className="mt-5 text-[11px] text-ink-400">Built for connected insurance operations · KES pricing where configured</p>
          </div>
          {[
            ["Platform", [["Insurance lines", "#lines"], ["Ecosystem", "#ecosystem"], ["Providers", "#providers"], ["Sign in", "/login"]]],
            ["Company", [["About", "#ecosystem"], ["Security", "#platform"]]],
          ].map(([title, links]) => (
            <div key={title}><p className="text-xs font-bold uppercase tracking-[0.12em] text-ink-950">{title}</p><div className="mt-4 space-y-2.5">{links.map(([label, href]) => href.startsWith("/") ? <Link key={label} to={href} className="block text-sm text-ink-500 hover:text-ink-900">{label}</Link> : <a key={label} href={href} className="block text-sm text-ink-500 hover:text-ink-900">{label}</a>)}</div></div>
          ))}
        </div>
        <div className="mx-auto flex max-w-7xl flex-col gap-2 border-t border-ink-200/60 px-4 py-5 text-[11px] text-ink-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} InsureConnect. All rights reserved.</p>
          <p>Insurance is issued by licensed providers. InsureConnect is the technology platform.</p>
        </div>
      </footer>
    </div>
  );
}
