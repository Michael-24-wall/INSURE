import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { DEMO_ACCOUNTS, HOME_BY_ROLE } from "../../lib/constants";
import { getErrorMessage } from "../../api/client";
import AuthLayout from "./AuthLayout";
import { Alert, Button, Input } from "../../components/ui";

export default function Login() {
  const { login, verifyTwoFactor } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [otp, setOtp] = useState({ required: false, challenge: "", code: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const notice = location.state?.notice;

  function goHome(user) {
    navigate(location.state?.from || HOME_BY_ROLE[user.role] || "/app", { replace: true });
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result?.otp_required) {
        setOtp({ required: true, challenge: result.challenge, code: "" });
      } else {
        goHome(result);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function onSubmitOtp(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await verifyTwoFactor(otp.challenge, otp.code);
      goHome(user);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Welcome back"
      title="Sign in to your workspace"
      description="Access your cover, claims, quotes or provider operations."
    >
      {notice && <div className="mb-4"><Alert tone="success">{notice}</Alert></div>}
      {otp.required ? (
        <form onSubmit={onSubmitOtp} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <div className="flex items-center gap-2 text-ink-700">
            <ShieldCheck className="h-5 w-5 text-brand-600" />
            <p className="text-sm font-bold">Two-factor authentication</p>
          </div>
          <p className="text-xs leading-relaxed text-ink-500">Enter the code from your authenticator app for <strong>{email}</strong>.</p>
          <Input
            label="Authentication code"
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            value={otp.code}
            onChange={(event) => setOtp((current) => ({ ...current, code: event.target.value }))}
            placeholder="6-digit code"
          />
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={() => { setOtp({ required: false, challenge: "", code: "" }); setError(""); }}>Back</Button>
            <Button type="submit" className="flex-1" loading={loading} icon={ShieldCheck} size="lg">Verify &amp; sign in</Button>
          </div>
        </form>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input
            label="Email address"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
          <div>
            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                className="pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="absolute bottom-2.5 right-3 rounded-lg p-1.5 text-ink-400 hover:bg-ink-100"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <div className="mt-2 text-right">
              <Link to="/forgot-password" className="text-xs font-semibold text-brand-700 hover:underline">Forgot password?</Link>
            </div>
          </div>
          <Button type="submit" className="w-full" loading={loading} icon={LogIn} size="lg">
            Sign in
          </Button>
        </form>
      )}

      {import.meta.env.DEV && (
        <div className="mt-6 rounded-2xl border border-ink-100 bg-white p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink-400">Demo accounts</p>
          <p className="mt-1 text-[11px] text-ink-400">Seeded for local evaluation. Tap to fill credentials.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                onClick={() => {
                  setEmail(account.email);
                  setPassword(account.password);
                  setError("");
                }}
                className="rounded-lg border border-ink-200 px-2.5 py-1.5 text-[11px] font-semibold text-ink-600 transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              >
                {account.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="mt-6 text-center text-sm text-ink-500">
        New to InsureConnect? <Link to="/register" className="link">Create an account</Link>
      </p>
    </AuthLayout>
  );
}
