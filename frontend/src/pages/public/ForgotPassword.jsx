import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Mail } from "lucide-react";
import api, { getErrorMessage } from "../../api/client";
import AuthLayout from "./AuthLayout";
import { Alert, Button, Input } from "../../components/ui";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/password/reset/", { email });
      setResult(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout eyebrow="Account recovery" title="Reset your password" description="Enter the email linked to your account and we’ll generate a secure reset token.">
      {result ? (
        <div className="space-y-4">
          <Alert tone="success">{result.detail}</Alert>
          {result.reset_token ? (
            <div className="rounded-2xl border border-ink-200 bg-white p-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Local reset token</p>
              <p className="mt-2 break-all font-mono text-xs text-ink-700">{result.reset_token}</p>
              <Link to={`/reset-password?token=${result.reset_token}`} className="mt-4 inline-flex">
                <Button size="sm">Open reset form <ArrowRight className="h-3.5 w-3.5" /></Button>
              </Link>
            </div>
          ) : (
            <p className="text-sm text-ink-500">Check your inbox for the reset link.</p>
          )}
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Input label="Email address" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
          <Button type="submit" className="w-full" loading={loading} icon={Mail}>Send reset instructions</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-ink-500">
        Remembered it? <Link to="/login" className="link">Back to sign in</Link>
      </p>
    </AuthLayout>
  );
}
