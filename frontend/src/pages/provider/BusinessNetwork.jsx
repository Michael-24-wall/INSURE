import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Handshake, Network } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { titleize } from "../../lib/format";
import { Alert, Button, Input, Modal, PageHeader, PageLoader, Stat, StatusBadge, Tabs, Textarea } from "../../components/ui";

export default function ProviderBusinessNetwork() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("dealerships");
  const [requestDealer, setRequestDealer] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [termsFor, setTermsFor] = useState(null);
  const [terms, setTerms] = useState({ commission_type: "percentage", rate: "10", fixed_amount: "" });
  const orgId = user?.memberships?.find((m) => m.organization_type === "insurer")?.organization_id;

  const dealers = useQuery({ queryKey: ["network-dealerships"], queryFn: async () => (await api.get("/business-network/dealerships/?page_size=100")).data });
  const partnerships = useQuery({ queryKey: ["partnerships"], queryFn: async () => (await api.get("/business-network/partnerships/?page_size=100")).data });
  const requests = useQuery({ queryKey: ["partnership-requests"], queryFn: async () => (await api.get("/business-network/partnership-requests/?page_size=100")).data });

  const sendRequest = useMutation({
    mutationFn: async () => (await api.post("/business-network/partnership-requests/", { from_organization: orgId, to_organization: requestDealer.id, message })).data,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["partnership-requests"] }); queryClient.invalidateQueries({ queryKey: ["network-dealerships"] }); toast.push("Request sent.", "success"); setRequestDealer(null); setMessage(""); },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const respond = useMutation({
    mutationFn: async ({ id, action }) => (await api.post(`/business-network/partnership-requests/${id}/respond/`, { action })).data,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["partnership-requests"] }); queryClient.invalidateQueries({ queryKey: ["partnerships"] }); toast.push("Updated.", "success"); },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const suspendPartnership = useMutation({
    mutationFn: async ({ id, reason }) => (await api.post(`/business-network/partnerships/${id}/suspend/`, { reason })).data,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["partnerships"] }); queryClient.invalidateQueries({ queryKey: ["partnership-requests"] }); toast.push("Partnership suspended.", "success"); },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const addTerms = useMutation({
    mutationFn: async () => {
      const payload = terms.commission_type === "percentage"
        ? { commission_type: "percentage", rate: terms.rate || "0", fixed_amount: "0" }
        : { commission_type: "fixed", rate: "0", fixed_amount: terms.fixed_amount || "0" };
      return (await api.post(`/business-network/partnerships/${termsFor.id}/commission-terms/`, payload)).data;
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["partnerships"] }); toast.push("Commission terms saved.", "success"); setTermsFor(null); },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (dealers.isLoading || partnerships.isLoading || requests.isLoading) return <PageLoader />;
  if (dealers.isError || partnerships.isError || requests.isError) {
    return (
      <div className="surface p-5">
        <Alert title="We couldn't load the business network.">Please refresh the page to try again.</Alert>
      </div>
    );
  }

  const dealerRows = listData(dealers.data);
  const partnerRows = listData(partnerships.data);
  const requestRows = listData(requests.data);

  return (
    <div>
      <PageHeader eyebrow="Business network" title="Dealer partnerships" description="Discover dealerships, approve partnerships and set referral commission terms." />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={Handshake} label="Active dealerships" value={partnerRows.filter((p) => p.status === "active").length} tone="brand" />
        <Stat icon={Building2} label="Verified dealerships" value={dealerRows.length} tone="blue" />
        <Stat icon={Network} label="Pending requests" value={requestRows.filter((r) => r.status === "pending").length} tone="amber" />
      </div>

      {error && <div className="mb-4"><Alert>{error}</Alert></div>}

      <Tabs active={tab} onChange={setTab} tabs={[
        { value: "dealerships", label: "Discover dealerships" },
        { value: "partnerships", label: "My partnerships" },
        { value: "requests", label: "Requests" },
      ]} />

      <div className="mt-6">
        {tab === "dealerships" && (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {dealerRows.map((d) => (
              <div key={d.id} className="surface flex flex-col gap-3 p-5">
                <div className="flex items-center gap-3">
                  {d.logo ? <img src={d.logo} alt={d.name} className="h-12 w-12 rounded-xl object-cover" /> : <span className="grid h-12 w-12 place-items-center rounded-xl bg-navy-500 text-white"><Building2 className="h-6 w-6" /></span>}
                  <div>
                    <p className="font-display text-sm font-bold text-ink-950">{d.name}</p>
                    <p className="text-[11px] text-ink-500">{d.county || d.country} · {d.branch_count} branches</p>
                  </div>
                </div>
                <p className="line-clamp-2 text-xs text-ink-500">{d.description}</p>
                <div className="mt-auto flex items-center justify-between">
                  <StatusBadge status={d.status} />
                  {d.partnership_status === "none" ? (
                    <Button size="sm" variant="brand" onClick={() => setRequestDealer(d)}>Request partnership</Button>
                  ) : (
                    <span className="text-xs font-semibold text-brand-700">{titleize(d.partnership_status)}</span>
                  )}
                </div>
              </div>
            ))}
            {!dealerRows.length && <p className="text-sm text-ink-500">No verified dealerships.</p>}
          </div>
        )}

        {tab === "partnerships" && (
          <div className="surface divide-y divide-ink-100">
            {partnerRows.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-xs font-bold text-ink-900">{p.dealership_name}</p>
                  <p className="mt-0.5 text-[11px] text-ink-400">Effective {p.effective_date || "—"}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={p.status} />
                  {p.status === "active" && <Button size="sm" variant="secondary" onClick={() => setTermsFor(p)}>Commission terms</Button>}
                  {p.status === "active" && <Button size="sm" variant="danger-soft" onClick={() => suspendPartnership.mutate({ id: p.id, reason: "Suspended by the insurer." })}>Suspend</Button>}
                </div>
              </div>
            ))}
            {!partnerRows.length && <p className="p-6 text-sm text-ink-500">No partnerships yet.</p>}
          </div>
        )}

        {tab === "requests" && (
          <div className="surface divide-y divide-ink-100">
            {requestRows.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-xs font-bold text-ink-900">{r.from_name} → {r.to_name}</p>
                  <p className="mt-0.5 text-[11px] text-ink-400">{r.message}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={r.status} />
                  {r.to_organization === orgId && r.status === "pending" && (
                    <>
                      <Button size="sm" variant="brand" onClick={() => respond.mutate({ id: r.id, action: "approve" })}>Approve</Button>
                      <Button size="sm" variant="danger-soft" onClick={() => respond.mutate({ id: r.id, action: "reject" })}>Reject</Button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {!requestRows.length && <p className="p-6 text-sm text-ink-500">No partnership requests.</p>}
          </div>
        )}
      </div>

      <Modal open={Boolean(requestDealer)} onClose={() => setRequestDealer(null)} title={`Partner with ${requestDealer?.name}`} footer={<><Button variant="secondary" onClick={() => setRequestDealer(null)}>Cancel</Button><Button onClick={() => sendRequest.mutate()} loading={sendRequest.isPending}>Send request</Button></>}>
        <Textarea label="Message" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Describe the partnership you have in mind." />
      </Modal>

      <Modal open={Boolean(termsFor)} onClose={() => setTermsFor(null)} title={`Commission terms — ${termsFor?.dealership_name}`} footer={<><Button variant="secondary" onClick={() => setTermsFor(null)}>Cancel</Button><Button onClick={() => addTerms.mutate()} loading={addTerms.isPending}>Save</Button></>}>
        <div className="space-y-4">
          <Tabs active={terms.commission_type} onChange={(v) => setTerms((c) => ({ ...c, commission_type: v }))} tabs={[{ value: "percentage", label: "Percentage" }, { value: "fixed", label: "Fixed" }]} />
          {terms.commission_type === "percentage"
            ? <Input label="Rate (%)" type="number" value={terms.rate} onChange={(e) => setTerms((c) => ({ ...c, rate: e.target.value }))} />
            : <Input label="Fixed amount (KES)" type="number" value={terms.fixed_amount} onChange={(e) => setTerms((c) => ({ ...c, fixed_amount: e.target.value }))} />}
        </div>
      </Modal>
    </div>
  );
}
