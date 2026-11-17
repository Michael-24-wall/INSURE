import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { BadgeCheck, Building2, KeyRound, ShieldCheck, UserRound } from "lucide-react";
import api, { getErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { formatDate, titleize } from "../lib/format";
import { ROLE_LABELS } from "../lib/constants";
import { Alert, Button, Input, PageHeader, PageLoader, StatusBadge } from "../components/ui";
import { DetailItem } from "../components/DataTable";

const PROFILE_FIELDS = {
  customer: ["national_id", "date_of_birth", "address", "city", "county"],
  agent: ["license_number", "region"],
  inspector: ["certification_number", "region", "capacity_per_day"],
};

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({ first_name: "", last_name: "", phone: "" });
  const [profile, setProfile] = useState({});
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm: "" });
  const [weather, setWeather] = useState({ error: "", success: "" });
  const [twoFactor, setTwoFactor] = useState({ step: null, secret: "", uri: "", code: "", password: "" });

  const query = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/auth/me/")).data,
  });

  useEffect(() => {
    if (!query.data) return;
    const me = query.data;
    setForm({ first_name: me.first_name || "", last_name: me.last_name || "", phone: me.phone || "" });
    const key = `${me.role}_profile`;
    setProfile(me[key] || {});
  }, [query.data]);

  const save = useMutation({
    mutationFn: async () => (await api.patch("/auth/me/", { ...form, ...profile })).data,
    onSuccess: (data) => {
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      setWeather({ error: "", success: "Profile updated." });
      toast.push("Profile updated.", "success");
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  const changePassword = useMutation({
    mutationFn: async () => (await api.post("/auth/password/change/", {
      current_password: passwords.current_password,
      new_password: passwords.new_password,
    })).data,
    onSuccess: async () => {
      toast.push("Password changed. Please sign in again.", "success");
      await logout();
      navigate("/login");
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  const submitKyc = useMutation({
    mutationFn: async () => (await api.post("/auth/kyc/", {
      national_id: profile.national_id || "",
      date_of_birth: profile.date_of_birth || null,
      address: profile.address || "",
      city: profile.city || "",
      county: profile.county || "",
    })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.push("KYC submitted for review.", "success");
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  const setupTwoFactor = useMutation({
    mutationFn: async () => (await api.post("/auth/2fa/setup/")).data,
    onSuccess: (data) => {
      setTwoFactor((current) => ({ ...current, step: "confirm", secret: data.secret, uri: data.uri }));
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  const confirmTwoFactor = useMutation({
    mutationFn: async () => (await api.post("/auth/2fa/confirm/", { code: twoFactor.code })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.push("Two-factor authentication enabled.", "success");
      setTwoFactor({ step: null, secret: "", uri: "", code: "", password: "" });
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  const disableTwoFactor = useMutation({
    mutationFn: async () => (await api.post("/auth/2fa/disable/", { password: twoFactor.password })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.push("Two-factor authentication disabled.", "success");
      setTwoFactor({ step: null, secret: "", uri: "", code: "", password: "" });
    },
    onError: (err) => setWeather({ error: getErrorMessage(err), success: "" }),
  });

  if (query.isLoading) return <PageLoader />;
  const me = query.data || user;
  const profileKey = `${me?.role}_profile`;
  const profileFields = PROFILE_FIELDS[me?.role] || [];

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateProfile(field, value) {
    setProfile((current) => ({ ...current, [field]: value }));
  }

  function submitPassword(event) {
    event.preventDefault();
    setWeather({ error: "", success: "" });
    if (passwords.new_password !== passwords.confirm) {
      setWeather({ error: "New passwords do not match.", success: "" });
      return;
    }
    changePassword.mutate();
  }

  return (
    <div>
      <PageHeader eyebrow="Account" title="Profile & security" description="Manage your personal details, role profile and sign-in credentials." />

      {weather.error && <div className="mb-4"><Alert>{weather.error}</Alert></div>}
      {weather.success && <div className="mb-4"><Alert tone="success">{weather.success}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <div className="surface p-6">
            <div className="flex items-center gap-2">
              <UserRound className="h-4 w-4 text-brand-600" />
              <h2 className="font-display text-lg font-bold text-ink-950">Personal details</h2>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Input label="First name" value={form.first_name} onChange={(event) => update("first_name", event.target.value)} />
              <Input label="Last name" value={form.last_name} onChange={(event) => update("last_name", event.target.value)} />
              <Input label="Email" value={me.email} disabled hint="Email changes require support verification." />
              <Input label="Phone" value={form.phone} onChange={(event) => update("phone", event.target.value)} />
              {profileFields.map((field) => (
                <Input
                  key={field}
                  label={titleize(field)}
                  type={field === "date_of_birth" ? "date" : field === "capacity_per_day" ? "number" : "text"}
                  value={profile[field] || ""}
                  onChange={(event) => updateProfile(field, event.target.value)}
                />
              ))}
            </div>
            <div className="mt-5 flex justify-end">
              <Button onClick={() => save.mutate()} loading={save.isPending}>Save changes</Button>
            </div>
          </div>

          <form onSubmit={submitPassword} className="surface p-6">
            <div className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-brand-600" />
              <h2 className="font-display text-lg font-bold text-ink-950">Change password</h2>
            </div>
            <p className="mt-1 text-xs text-ink-400">Changing your password signs you out of all active sessions.</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <Input label="Current password" type="password" required value={passwords.current_password} onChange={(event) => setPasswords((current) => ({ ...current, current_password: event.target.value }))} />
              <Input label="New password" type="password" required value={passwords.new_password} onChange={(event) => setPasswords((current) => ({ ...current, new_password: event.target.value }))} />
              <Input label="Confirm new password" type="password" required value={passwords.confirm} onChange={(event) => setPasswords((current) => ({ ...current, confirm: event.target.value }))} />
            </div>
            <div className="mt-5 flex justify-end">
              <Button type="submit" variant="secondary" loading={changePassword.isPending}>Update password</Button>
            </div>
          </form>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6 text-white">
            <div className="flex items-start justify-between">
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-lime-300 font-display text-lg font-bold text-ink-950">{me.full_name?.split(" ").map((part) => part[0]).slice(0, 2).join("")}</span>
              <BadgeCheck className="h-6 w-6 text-lime-300" />
            </div>
            <p className="mt-4 font-display text-xl font-bold">{me.full_name}</p>
            <p className="text-sm text-white/50">{me.email}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">{ROLE_LABELS[me.role] || me.role}</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">{me.email_verified ? "Email verified" : "Email unverified"}</span>
            </div>
          </div>

          <div className="surface p-5">
            <h2 className="font-display text-base font-bold text-ink-950">Account details</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              <DetailItem label="Member since">{formatDate(me.created_at)}</DetailItem>
              <DetailItem label="Account status"><StatusBadge status={me.is_active ? "active" : "suspended"} /></DetailItem>
              {me[profileKey]?.kyc_status && <DetailItem label="KYC status"><StatusBadge status={me[profileKey].kyc_status} /></DetailItem>}
              {me[profileKey]?.is_verified !== undefined && <DetailItem label="Verified"><StatusBadge status={me[profileKey].is_verified ? "verified" : "pending"} /></DetailItem>}
              {me.agent_profile?.commission_rate && <DetailItem label="Commission rate">{me.agent_profile.commission_rate}%</DetailItem>}
            </div>
          </div>

          {me.role === "customer" && me[profileKey] && (
            <div className="surface p-5">
              <div className="flex items-center gap-2">
                <BadgeCheck className="h-4 w-4 text-brand-600" />
                <h2 className="font-display text-base font-bold text-ink-950">Identity verification (KYC)</h2>
              </div>
              <p className="mt-1 text-xs text-ink-400">Your policy can only be issued once your identity is verified.</p>
              <div className="mt-3 space-y-3">
                {me[profileKey].kyc_notes && <p className="rounded-lg bg-ink-50 p-2.5 text-xs text-ink-600">{me[profileKey].kyc_notes}</p>}
                {["unverified", "rejected"].includes(me[profileKey].kyc_status) && (
                  <Button onClick={() => submitKyc.mutate()} loading={submitKyc.isPending}>Submit for review</Button>
                )}
                {me[profileKey].kyc_status === "pending" && <Alert tone="info">Your documents are pending review.</Alert>}
              </div>
            </div>
          )}

          {me.memberships?.length > 0 && (
            <div className="surface p-5">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-brand-600" />
                <h2 className="font-display text-base font-bold text-ink-950">Organizations</h2>
              </div>
              <div className="mt-4 space-y-3">
                {me.memberships.map((membership) => (
                  <div key={`${membership.organization_id}-${membership.role}`} className="rounded-xl border border-ink-100 p-3">
                    <p className="text-xs font-bold text-ink-900">{membership.organization_name}</p>
                    <p className="mt-0.5 text-[10px] text-ink-400">{titleize(membership.organization_type)} · {titleize(membership.role)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="surface p-5">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <h2 className="font-display text-base font-bold text-ink-950">Two-factor authentication</h2>
            </div>
            {me.totp_enabled ? (
              <div className="mt-3 space-y-3">
                <p className="text-xs text-ink-500">Enabled. You&apos;ll enter a code from your authenticator app when signing in.</p>
                {twoFactor.step === "disable" ? (
                  <div className="space-y-2">
                    <Input label="Password" type="password" value={twoFactor.password} onChange={(event) => setTwoFactor((c) => ({ ...c, password: event.target.value }))} placeholder="Confirm your password" />
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setTwoFactor((c) => ({ ...c, step: null, password: "" }))}>Cancel</Button>
                      <Button size="sm" variant="danger" onClick={() => disableTwoFactor.mutate()} loading={disableTwoFactor.isPending}>Disable</Button>
                    </div>
                  </div>
                ) : (
                  <Button size="sm" variant="secondary" onClick={() => setTwoFactor((c) => ({ ...c, step: "disable", password: "" }))}>Disable</Button>
                )}
              </div>
            ) : twoFactor.step === "confirm" ? (
              <div className="mt-3 space-y-3">
                <p className="text-xs text-ink-500">Add this key to your authenticator app, then enter the code it generates.</p>
                <div className="rounded-lg bg-ink-50 p-2.5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-ink-400">Secret key</p>
                  <p className="mt-1 break-all font-mono text-xs text-ink-700">{twoFactor.secret}</p>
                </div>
                <Input label="Authentication code" value={twoFactor.code} onChange={(event) => setTwoFactor((c) => ({ ...c, code: event.target.value }))} placeholder="6-digit code" />
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setTwoFactor({ step: null, secret: "", uri: "", code: "", password: "" })}>Cancel</Button>
                  <Button size="sm" onClick={() => confirmTwoFactor.mutate()} loading={confirmTwoFactor.isPending}>Confirm</Button>
                </div>
              </div>
            ) : (
              <div className="mt-3">
                <p className="text-xs text-ink-500">Add an extra layer of security to your account.</p>
                <Button size="sm" className="mt-3" onClick={() => setupTwoFactor.mutate()} loading={setupTwoFactor.isPending}>Enable</Button>
              </div>
            )}
          </div>

          <div className="surface p-5">
            <div className="flex items-center gap-2 text-ink-900"><ShieldCheck className="h-4 w-4 text-emerald-600" /><p className="text-sm font-bold">Security tip</p></div>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">Never share your password or one-time codes. InsureConnect staff will never ask for them.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
