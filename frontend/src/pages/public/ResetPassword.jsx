import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { KeyRound } from "lucide-react";
import api, { getErrorMessage } from "../../api/client";
import AuthLayout from "./AuthLayout";
import { Alert, Button, Input } from "../../components/ui";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(searchParams.get("token") || "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/password/reset/confirm/", { token, new_password: password });
      navigate("/login", { replace: true, state: { notice: "Password reset. Please sign in." } });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout eyebrow="Account recovery" title="Choose a new password" description="Paste your reset token and set a strong new password.">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Input label="Reset token" required value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste the token" className="font-mono text-xs" />
        <Input label="New password" type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
        <Input label="Confirm new password" type="password" required minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        <Button type="submit" className="w-full" loading={loading} icon={KeyRound}>Reset password</Button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-500">
        Need a new token? <Link to="/forgot-password" className="link">Request one</Link>
      </p>
    </AuthLayout>
  );
}
