import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BadgeCheck,
  Bell,
  Bot,
  Building2,
  CalendarCheck,
  Car,
  ClipboardList,
  FileSearch,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Package,
  ReceiptText,
  ScrollText,
  Settings,
  ShieldCheck,
  Store,
  TriangleAlert,
  UserRound,
  Users,
  Wallet,
  X,
  ChevronDown,
} from "lucide-react";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS } from "../lib/constants";
import { initials } from "../lib/format";
import { Brand } from "./Brand";
import { AIAssistant } from "./AIAssistant";
import { Badge, cn } from "./ui";

const customerNav = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/app/vehicles", label: "My vehicles", icon: Car },
  { to: "/app/marketplace", label: "Get a quote", icon: Store },
  { to: "/app/quotes", label: "Quotations", icon: FileSearch },
  { to: "/app/applications", label: "Applications", icon: ClipboardList },
  { to: "/app/policies", label: "Policies", icon: ShieldCheck },
  { to: "/app/claims", label: "Claims", icon: TriangleAlert },
  { to: "/app/payments", label: "Payments", icon: Wallet },
];

const providerNav = [
  { to: "/provider", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/provider/network", label: "Business network", icon: Network },
  { to: "/provider/products", label: "Products", icon: Package },
  { to: "/provider/quotes", label: "Quote requests", icon: FileSearch },
  { to: "/provider/applications", label: "Applications", icon: ClipboardList },
  { to: "/provider/policies", label: "Policies", icon: ShieldCheck },
  { to: "/claims", label: "Claims", icon: TriangleAlert },
  { to: "/provider/payments", label: "Payments", icon: Wallet },
  { to: "/inspections", label: "Inspections", icon: CalendarCheck },
];

const dealerNav = [
  { to: "/dealer", label: "Business network", icon: Network, end: true },
  { to: "/dealer/quotes", label: "Quotations", icon: FileSearch },
  { to: "/dealer/applications", label: "Applications", icon: ClipboardList },
];

const inspectorNav = [
  { to: "/inspector", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/inspector/inspections", label: "My inspections", icon: CalendarCheck },
];

const claimsNav = [
  { to: "/claims", label: "Claims workspace", icon: TriangleAlert, end: true },
  { to: "/inspections", label: "Inspections", icon: CalendarCheck },
];

const adminNav = [
  { to: "/admin", label: "Overview", icon: Gauge, end: true },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/organizations", label: "Organizations", icon: Building2 },
  { to: "/claims", label: "Claims", icon: TriangleAlert },
  { to: "/inspections", label: "Inspections", icon: CalendarCheck },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText },
  { to: "/admin/settings", label: "Settings", icon: Settings },
];

const agentNav = [
  { to: "/agent", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/agent/policies", label: "Policies", icon: ShieldCheck },
  { to: "/agent/commissions", label: "Commissions", icon: ReceiptText },
];

function navForRole(role) {
  if (role === "customer") return customerNav;
  if (["provider_admin", "provider_staff"].includes(role)) return providerNav;
  if (["dealer_admin", "dealer_staff"].includes(role)) return dealerNav;
  if (role === "inspector") return inspectorNav;
  if (role === "claims_officer") return claimsNav;
  if (["admin", "super_admin"].includes(role)) return adminNav;
  if (role === "agent") return agentNav;
  return customerNav;
}

const detailTitles = [
  ["/app/quotes/", "Quotation detail"],
  ["/app/vehicles/", "Vehicle detail"],
  ["/app/applications/", "Application detail"],
  ["/app/policies/", "Policy detail"],
  ["/app/claims/", "Claim detail"],
  ["/provider/quotes/", "Quotation detail"],
  ["/provider/applications/", "Application detail"],
  ["/provider/policies/", "Policy detail"],
  ["/inspector/inspections/", "Inspection detail"],
  ["/inspections/", "Inspection detail"],
  ["/claims/", "Claim detail"],
  ["/agent/policies/", "Policy detail"],
];

function titleFor(pathname) {
  if (pageTitles[pathname]) return pageTitles[pathname];
  for (const [prefix, title] of detailTitles) {
    if (pathname.startsWith(prefix)) return title;
  }
  return "Workspace";
}

const pageTitles = {
  "/app": "Overview",
  "/app/vehicles": "My vehicles",
  "/app/marketplace": "Get a quote",
  "/app/quotes": "Quotations",
  "/app/applications": "Applications",
  "/app/policies": "Policies",
  "/app/claims": "Claims",
  "/app/payments": "Payments",
  "/provider": "Provider overview",
  "/provider/products": "Products",
  "/provider/quotes": "Quote requests",
  "/provider/applications": "Applications",
  "/provider/policies": "Policies",
  "/provider/payments": "Payments",
  "/inspector": "Inspector overview",
  "/inspector/inspections": "My inspections",
  "/claims": "Claims workspace",
  "/inspections": "Inspections",
  "/admin": "Platform overview",
  "/admin/users": "Users",
  "/admin/organizations": "Organizations",
  "/admin/audit": "Audit log",
  "/admin/settings": "Platform settings",
  "/agent": "Agent overview",
  "/agent/policies": "Policies",
  "/agent/commissions": "Commissions",
  "/dealer": "Business network",
  "/dealer/quotes": "Quotations",
  "/dealer/applications": "Applications",
  "/provider/network": "Business network",
  "/notifications": "Notifications",
  "/profile": "Profile",
};

export function AppShell() {
  const { user, logout, homePath } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const nav = useMemo(() => navForRole(user?.role), [user?.role]);
  const title = titleFor(location.pathname);

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => (await api.get("/notifications/unread-count/")).data,
    refetchInterval: 60000,
    enabled: Boolean(user),
  });

  useEffect(() => {
    setMobileOpen(false);
    setUserMenuOpen(false);
  }, [location.pathname]);

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-ink-50">
      {mobileOpen && <div className="fixed inset-0 z-40 bg-ink-950/50 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[272px] flex-col bg-ink-950 text-white transition-transform duration-300 lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-[76px] items-center justify-between px-5">
          <Brand to={homePath} light />
          <button onClick={() => setMobileOpen(false)} className="rounded-lg p-2 text-white/60 hover:bg-white/10 lg:hidden" aria-label="Close navigation">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mx-4 mb-3 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-500 font-display text-sm font-bold text-white">
            {initials(user?.full_name || user?.email)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{user?.full_name || user?.email}</p>
            <p className="truncate text-[11px] text-white/50">{ROLE_LABELS[user?.role] || user?.role}</p>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-2">
          <p className="px-3 pb-2 pt-2 text-[10px] font-bold uppercase tracking-[0.18em] text-white/30">Workspace</p>
          <div className="space-y-1">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                    isActive ? "bg-brand-500 text-white" : "text-white/65 hover:bg-white/8 hover:text-white"
                  )
                }
              >
                <item.icon className="h-4.5 w-4.5 h-[18px] w-[18px]" />
                {item.label}
              </NavLink>
            ))}
          </div>

          <p className="px-3 pb-2 pt-5 text-[10px] font-bold uppercase tracking-[0.18em] text-white/30">Account</p>
          <div className="space-y-1">
            <NavLink
              to="/notifications"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  isActive ? "bg-brand-500 text-white" : "text-white/65 hover:bg-white/8 hover:text-white"
                )
              }
            >
              <Bell className="h-[18px] w-[18px]" />
              Notifications
              {unread?.count > 0 && (
                <span className="ml-auto grid min-w-5 place-items-center rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{unread.count}</span>
              )}
            </NavLink>
            <NavLink
              to="/profile"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  isActive ? "bg-brand-500 text-white" : "text-white/65 hover:bg-white/8 hover:text-white"
                )
              }
            >
              <UserRound className="h-[18px] w-[18px]" />
              Profile
            </NavLink>
          </div>
        </nav>

        <div className="border-t border-white/10 p-3">
          <button
            onClick={() => setAssistantOpen(true)}
            className="flex w-full items-center gap-3 rounded-xl bg-gradient-to-r from-brand-600/30 to-brand-300/10 px-3 py-3 text-left transition hover:from-brand-600/40"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white">
              <Bot className="h-4 w-4" />
            </span>
            <div>
              <p className="text-xs font-bold">Ask the assistant</p>
              <p className="text-[10px] text-white/45">Cover, claims & payments</p>
            </div>
          </button>
        </div>
      </aside>

      <div className="lg:pl-[272px]">
        <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between gap-3 border-b border-ink-100 bg-white/85 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 lg:hidden" aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">InsureConnect</p>
              <h2 className="truncate font-display text-base font-bold text-ink-950">{title}</h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setAssistantOpen(true)}
              className="hidden items-center gap-2 rounded-xl border border-ink-200 bg-white px-3 py-2 text-xs font-semibold text-ink-600 hover:border-brand-300 hover:text-brand-700 sm:flex"
            >
              <Bot className="h-4 w-4 text-brand-600" /> AI assistant
            </button>
            <Link to="/notifications" className="relative rounded-xl border border-ink-200 bg-white p-2.5 text-ink-500 hover:text-ink-900" aria-label="Notifications">
              <Bell className="h-4 w-4" />
              {unread?.count > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white" />}
            </Link>
            <div className="relative">
              <button onClick={() => setUserMenuOpen((open) => !open)} className="flex items-center gap-2 rounded-xl border border-ink-200 bg-white py-1.5 pl-1.5 pr-2.5 hover:border-ink-300">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink-950 text-xs font-bold text-brand-300">{initials(user?.full_name || user?.email)}</span>
                <ChevronDown className="h-3.5 w-3.5 text-ink-400" />
              </button>
              {userMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                  <div className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-ink-100 bg-white p-2 shadow-soft">
                    <div className="border-b border-ink-100 px-3 py-2.5">
                      <p className="truncate text-sm font-semibold text-ink-900">{user?.full_name}</p>
                      <p className="truncate text-xs text-ink-400">{user?.email}</p>
                      <Badge tone="green" className="mt-2">
                        <BadgeCheck className="mr-1 h-3 w-3" /> {ROLE_LABELS[user?.role]}
                      </Badge>
                    </div>
                    <Link to="/profile" className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-600 hover:bg-ink-50">
                      <UserRound className="h-4 w-4" /> Profile & security
                    </Link>
                    {["provider_admin", "provider_staff"].includes(user?.role) && (
                      <Link to="/provider/settings" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-600 hover:bg-ink-50">
                        <Building2 className="h-4 w-4" /> Organization
                      </Link>
                    )}
                    <button onClick={handleLogout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                      <LogOut className="h-4 w-4" /> Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>

      <AIAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}

export function RoleBadge({ role }) {
  return <Badge tone="green">{ROLE_LABELS[role] || role}</Badge>;
}
