import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/Layout";
import { ProtectedRoute, PublicOnlyRoute } from "./components/ProtectedRoute";

import Landing from "./pages/public/Landing";
import Login from "./pages/public/Login";
import Register from "./pages/public/Register";
import ForgotPassword from "./pages/public/ForgotPassword";
import ResetPassword from "./pages/public/ResetPassword";
import VerifyEmail from "./pages/public/VerifyEmail";
import NotFound from "./pages/public/NotFound";

import CustomerDashboard from "./pages/customer/CustomerDashboard";
import Vehicles from "./pages/customer/Vehicles";
import VehicleDetail from "./pages/customer/VehicleDetail";
import Marketplace from "./pages/customer/Marketplace";
import ProviderDashboard from "./pages/provider/ProviderDashboard";
import Products from "./pages/provider/Products";
import ProviderSettings from "./pages/provider/ProviderSettings";
import ProviderBusinessNetwork from "./pages/provider/BusinessNetwork";
import InspectorDashboard from "./pages/inspector/InspectorDashboard";
import AgentDashboard from "./pages/agent/AgentDashboard";
import Commissions from "./pages/agent/Commissions";
import DealerDashboard from "./pages/dealer/DealerDashboard";
import AdminUsers from "./pages/admin/Users";
import AdminOrganizations from "./pages/admin/Organizations";
import AuditLog from "./pages/admin/AuditLog";
import AdminSettings from "./pages/admin/Settings";

import Quotations from "./pages/Quotations";
import QuotationDetail from "./pages/QuotationDetail";
import Applications from "./pages/Applications";
import ApplicationDetail from "./pages/ApplicationDetail";
import Policies from "./pages/Policies";
import PolicyDetail from "./pages/PolicyDetail";
import Payments from "./pages/Payments";
import Claims from "./pages/claims/Claims";
import ClaimDetail from "./pages/claims/ClaimDetail";
import Inspections from "./pages/inspections/Inspections";
import InspectionDetail from "./pages/inspections/InspectionDetail";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";

const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));

const CUSTOMER = ["customer"];
const PROVIDER = ["provider_admin", "provider_staff"];
const ADMIN = ["admin", "super_admin"];
const CLAIMS = ["provider_admin", "provider_staff", "claims_officer", "admin", "super_admin"];
const INSPECTIONS = ["customer", "provider_admin", "provider_staff", "claims_officer", "inspector", "admin", "super_admin"];

export default function App() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-ink-50 text-sm text-ink-500">Loading…</div>}>
    <Routes>
      <Route path="/" element={<Landing />} />

      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
      </Route>
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/profile" element={<Profile />} />

          <Route element={<ProtectedRoute roles={CUSTOMER} />}>
            <Route path="/app" element={<CustomerDashboard />} />
            <Route path="/app/vehicles" element={<Vehicles />} />
            <Route path="/app/vehicles/:id" element={<VehicleDetail />} />
            <Route path="/app/marketplace" element={<Marketplace />} />
            <Route path="/app/quotes" element={<Quotations />} />
            <Route path="/app/quotes/:id" element={<QuotationDetail />} />
            <Route path="/app/applications" element={<Applications />} />
            <Route path="/app/applications/:id" element={<ApplicationDetail />} />
            <Route path="/app/policies" element={<Policies />} />
            <Route path="/app/policies/:id" element={<PolicyDetail />} />
            <Route path="/app/claims" element={<Claims />} />
            <Route path="/app/claims/:id" element={<ClaimDetail />} />
            <Route path="/app/payments" element={<Payments />} />
          </Route>

          <Route element={<ProtectedRoute roles={PROVIDER} />}>
            <Route path="/provider" element={<ProviderDashboard />} />
            <Route path="/provider/network" element={<ProviderBusinessNetwork />} />
            <Route path="/provider/products" element={<Products />} />
            <Route path="/provider/quotes" element={<Quotations />} />
            <Route path="/provider/quotes/:id" element={<QuotationDetail />} />
            <Route path="/provider/applications" element={<Applications />} />
            <Route path="/provider/applications/:id" element={<ApplicationDetail />} />
            <Route path="/provider/policies" element={<Policies />} />
            <Route path="/provider/policies/:id" element={<PolicyDetail />} />
            <Route path="/provider/payments" element={<Payments />} />
            <Route path="/provider/settings" element={<ProviderSettings />} />
          </Route>

          <Route element={<ProtectedRoute roles={["inspector"]} />}>
            <Route path="/inspector" element={<InspectorDashboard />} />
            <Route path="/inspector/inspections" element={<Inspections />} />
            <Route path="/inspector/inspections/:id" element={<InspectionDetail />} />
          </Route>

          <Route element={<ProtectedRoute roles={["agent"]} />}>
            <Route path="/agent" element={<AgentDashboard />} />
            <Route path="/agent/policies" element={<Policies />} />
            <Route path="/agent/policies/:id" element={<PolicyDetail />} />
            <Route path="/agent/commissions" element={<Commissions />} />
          </Route>

          <Route element={<ProtectedRoute roles={["dealer_admin", "dealer_staff"]} />}>
            <Route path="/dealer" element={<DealerDashboard />} />
            <Route path="/dealer/quotes" element={<Quotations />} />
            <Route path="/dealer/quotes/:id" element={<QuotationDetail />} />
            <Route path="/dealer/applications" element={<Applications />} />
            <Route path="/dealer/applications/:id" element={<ApplicationDetail />} />
          </Route>

          <Route element={<ProtectedRoute roles={ADMIN} />}>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/users" element={<AdminUsers />} />
            <Route path="/admin/organizations" element={<AdminOrganizations />} />
            <Route path="/admin/audit" element={<AuditLog />} />
            <Route path="/admin/settings" element={<AdminSettings />} />
          </Route>

          <Route element={<ProtectedRoute roles={CLAIMS} />}>
            <Route path="/claims" element={<Claims />} />
            <Route path="/claims/:id" element={<ClaimDetail />} />
          </Route>

          <Route element={<ProtectedRoute roles={INSPECTIONS} />}>
            <Route path="/inspections" element={<Inspections />} />
            <Route path="/inspections/:id" element={<InspectionDetail />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
    </Suspense>
  );
}
