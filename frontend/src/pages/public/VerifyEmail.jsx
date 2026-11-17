import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BadgeCheck, MailCheck } from "lucide-react";
import api, { getErrorMessage } from "../../api/client";
import AuthLayout from "./AuthLayout";
import { Alert, Button, Input, Spinner } from "../../components/ui";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") || "");
  const [state, setState] = useState({ status: "idle", message: "" });
  const attempted = useRef(false);

  const verify = useCallback(async (value = token) => {
    if (!value) {
      setState({ status: "error", message: "Enter the verification token from your email." });
      return;
    }
    setState({ status: "loading", message: "" });
    try {
      const { data } = await api.post("/auth/verify-email/", { token: value });
      setState({ status: "success", message: data.detail });
    } catch (err) {
      setState({ status: "error", message: getErrorMessage(err) });
    }
  }, [token]);

  useEffect(() => {
    if (token && !attempted.current) {
      attempted.current = true;
      verify(token);
    }
  }, [token, verify]);

  return (
    <AuthLayout eyebrow="Email verification" title="Verify your email address" description="Verification keeps your account secure and unlocks all platform features.">
      {state.status === "loading" && (
        <div className="flex items-center gap-3 rounded-2xl border border-ink-100 bg-white p-5 text-sm text-ink-500"><Spinner /> Verifying your token…</div>
      )}
      {state.status === "success" && (
        <div className="space-y-4">
          <Alert tone="success" title="Email verified">{state.message}</Alert>
          <Link to="/login"><Button className="w-full" icon={BadgeCheck}>Continue to sign in</Button></Link>
        </div>
      )}
      {state.status !== "success" && state.status !== "loading" && (
        <form onSubmit={(event) => { event.preventDefault(); verify(); }} className="space-y-4">
          {state.status === "error" && <Alert>{state.message}</Alert>}
          <Input label="Verification token" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste your token" className="font-mono text-xs" />
          <Button type="submit" className="w-full" icon={MailCheck}>Verify email</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm text-ink-500">
        <Link to="/login" className="link">Back to sign in</Link>
      </p>
    </AuthLayout>
  );
}
