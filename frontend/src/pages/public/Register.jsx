import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Building2, CheckCircle2, UserRound } from "lucide-react";
import api, { getErrorMessage } from "../../api/client";
import AuthLayout from "./AuthLayout";
import { Alert, Button, Input, Modal, Textarea } from "../../components/ui";
import { useToast } from "../../context/ToastContext";

const emptyForm = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  password: "",
  position: "",
  organization_name: "",
  trading_name: "",
  registration_number: "",
  tax_id: "",
  organization_email: "",
  organization_phone: "",
  website: "",
  address: "",
  country: "",
  county: "",
  description: "",
};

export default function Register() {
  const [searchParams] = useSearchParams();
  const [type, setType] = useState(searchParams.get("type") === "provider" ? "provider" : "customer");
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = type === "provider" ? "/auth/register/provider/" : type === "dealer" ? "/auth/register/dealer/" : "/auth/register/customer/";
      const payload = { ...form };
      if (type === "customer") {
        ["organization_name", "trading_name", "registration_number", "tax_id", "organization_email", "organization_phone", "website", "address", "country", "county", "description", "position"].forEach((field) => delete payload[field]);
      }
      const { data } = await api.post(endpoint, payload);
      setResult({ ...data, type });
      setVerifyOpen(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function verifyEmail() {
    if (!result?.verification_token) return;
    setVerifying(true);
    try {
      await api.post("/auth/verify-email/", { token: result.verification_token });
      setVerified(true);
      toast.push("Email verified. You can now sign in.", "success");
    } catch (err) {
      toast.push(getErrorMessage(err), "error");
    } finally {
      setVerifying(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Create an account"
      title="Start your insurance journey"
      description="Choose a customer or provider account. Provider organizations are reviewed before going live."
    >
      <div className="grid grid-cols-3 gap-2 rounded-2xl bg-ink-100/70 p-1.5">
        <button
          type="button"
          onClick={() => { setType("customer"); setError(""); }}
          className={`flex items-center justify-center gap-2 rounded-xl px-2 py-2.5 text-sm font-semibold transition ${type === "customer" ? "bg-white text-ink-950 shadow-sm" : "text-ink-500 hover:text-ink-800"}`}
        >
          <UserRound className="h-4 w-4" /> Customer
        </button>
        <button
          type="button"
          onClick={() => { setType("provider"); setError(""); }}
          className={`flex items-center justify-center gap-2 rounded-xl px-2 py-2.5 text-sm font-semibold transition ${type === "provider" ? "bg-white text-ink-950 shadow-sm" : "text-ink-500 hover:text-ink-800"}`}
        >
          <Building2 className="h-4 w-4" /> Insurer
        </button>
        <button
          type="button"
          onClick={() => { setType("dealer"); setError(""); }}
          className={`flex items-center justify-center gap-2 rounded-xl px-2 py-2.5 text-sm font-semibold transition ${type === "dealer" ? "bg-white text-ink-950 shadow-sm" : "text-ink-500 hover:text-ink-800"}`}
        >
          <Building2 className="h-4 w-4" /> Dealership
        </button>
      </div>

      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        {error && <Alert>{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="First name" required value={form.first_name} onChange={(event) => update("first_name", event.target.value)} />
          <Input label="Last name" required value={form.last_name} onChange={(event) => update("last_name", event.target.value)} />
        </div>
        <Input label="Email address" type="email" required value={form.email} onChange={(event) => update("email", event.target.value)} placeholder="you@example.com" />
        <Input label="Phone number" value={form.phone} onChange={(event) => update("phone", event.target.value)} placeholder="+254 7XX XXX XXX" />
        <Input label="Password" type="password" required minLength={8} value={form.password} onChange={(event) => update("password", event.target.value)} hint="At least 8 characters. Avoid common or numeric-only passwords." />

        {(type === "provider" || type === "dealer") && (
          <div className="space-y-4 rounded-2xl border border-ink-100 bg-white p-4">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-brand-600" />
              <p className="text-xs font-bold uppercase tracking-[0.1em] text-ink-500">{type === "dealer" ? "Dealership details" : "Company details"}</p>
            </div>
            <Input label={type === "dealer" ? "Registered dealership name" : "Registered company name"} required value={form.organization_name} onChange={(event) => update("organization_name", event.target.value)} />
            <Input label="Trading name" value={form.trading_name} onChange={(event) => update("trading_name", event.target.value)} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Registration number" value={form.registration_number} onChange={(event) => update("registration_number", event.target.value)} />
              <Input label="Tax ID" value={form.tax_id} onChange={(event) => update("tax_id", event.target.value)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Organization phone" value={form.organization_phone} onChange={(event) => update("organization_phone", event.target.value)} />
              <Input label="Organization email" type="email" value={form.organization_email} onChange={(event) => update("organization_email", event.target.value)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Country" value={form.country} onChange={(event) => update("country", event.target.value)} placeholder="Kenya" />
              <Input label="County / region" value={form.county} onChange={(event) => update("county", event.target.value)} />
            </div>
            <Input label="Your position" value={form.position} onChange={(event) => update("position", event.target.value)} placeholder="Managing Director" />
            <Input label="Website" type="url" value={form.website} onChange={(event) => update("website", event.target.value)} placeholder="https://" />
            <Textarea label="Address" value={form.address} onChange={(event) => update("address", event.target.value)} className="min-h-[80px]" />
            <Textarea label="Description" value={form.description} onChange={(event) => update("description", event.target.value)} className="min-h-[80px]" />
          </div>
        )}

        <label className="flex items-start gap-2.5 text-xs leading-relaxed text-ink-500">
          <input type="checkbox" required className="mt-0.5 h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500" />
          <span>I agree to the platform terms and confirm that the information provided is accurate.</span>
        </label>

        <Button type="submit" className="w-full" size="lg" loading={loading}>
          Create {type === "provider" ? "provider" : type === "dealer" ? "dealership" : "customer"} account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-500">
        Already have an account? <Link to="/login" className="link">Sign in</Link>
      </p>

      <Modal
        open={verifyOpen}
        onClose={() => {
          setVerifyOpen(false);
          if (verified) navigate("/login");
        }}
        title={verified ? "Email verified" : "Account created"}
        description={type === "provider" || type === "dealer" ? "Your organization has been submitted for verification." : "One small step to activate your account."}
        footer={
          verified ? (
            <Button onClick={() => navigate("/login")}>Continue to sign in</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => { setVerifyOpen(false); navigate("/login"); }}>I’ll verify later</Button>
              <Button onClick={verifyEmail} loading={verifying} disabled={!result?.verification_token}>Verify email now</Button>
            </>
          )
        }
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-2xl bg-brand-50 p-4 text-brand-900">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="text-sm leading-relaxed">
              <p className="font-bold">{result?.user?.full_name} · {result?.user?.email}</p>
              <p className="mt-1 text-brand-800/80">{result?.message}</p>
              {(type === "provider" || type === "dealer") && result?.organization && (
                <p className="mt-2 text-xs">Organization: <span className="font-semibold">{result.organization.name}</span> · Status: {result.organization.status}</p>
              )}
            </div>
          </div>
          {result?.verification_token ? (
            <div className="rounded-xl border border-ink-200 bg-ink-50 p-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Local verification token</p>
              <p className="mt-1 break-all font-mono text-[11px] text-ink-600">{result.verification_token}</p>
              <p className="mt-2 text-[10px] text-ink-400">Shown only while the backend is in DEBUG mode. Email is not configured locally.</p>
            </div>
          ) : (
            <p className="text-xs text-ink-400">Check your inbox for the verification link.</p>
          )}
        </div>
      </Modal>
    </AuthLayout>
  );
}
