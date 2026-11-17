import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, ClipboardCheck, CreditCard, FileText, ShieldCheck } from "lucide-react";
import api, { getErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { formatCurrency, formatDate, titleize, todayISO } from "../lib/format";
import { PAYMENT_METHODS } from "../lib/constants";
import { Alert, Button, Input, Modal, PageLoader, Select, StatusBadge, Textarea } from "../components/ui";
import { DetailItem } from "../components/DataTable";

const ACTIONS = {
  customer: {
    submitted: [],
    draft: [{ key: "submit", label: "Submit application", tone: "brand" }],
    approved: [{ key: "pay", label: "Pay premium", tone: "lime" }],
    more_info: [{ key: "withdraw", label: "Withdraw application", tone: "danger-soft" }],
  },
  provider: {
    submitted: [
      { key: "review", label: "Start review", tone: "brand" },
      { key: "info", label: "Request information", tone: "secondary" },
      { key: "approve", label: "Approve", tone: "lime" },
      { key: "reject", label: "Reject", tone: "danger-soft" },
    ],
    under_review: [
      { key: "info", label: "Request information", tone: "secondary" },
      { key: "approve", label: "Approve", tone: "lime" },
      { key: "reject", label: "Reject", tone: "danger-soft" },
    ],
    more_info: [{ key: "approve", label: "Approve", tone: "lime" }, { key: "reject", label: "Reject", tone: "danger-soft" }],
    approved: [{ key: "issue", label: "Issue policy", tone: "brand" }],
  },
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const isProvider = location.pathname.startsWith("/provider");
  const isDealer = location.pathname.startsWith("/dealer");
  const basePath = isDealer ? "/dealer" : isProvider ? "/provider" : "/app";
  const [modal, setModal] = useState(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [payMethod, setPayMethod] = useState("mpesa");
  const [phone, setPhone] = useState("");
  const [createdPayment, setCreatedPayment] = useState(null);
  const [issueForm, setIssueForm] = useState({ start_date: todayISO(1), end_date: todayISO(366), provider_reference: "" });

  const query = useQuery({
    queryKey: ["application", id],
    queryFn: async () => (await api.get(`/applications/${id}/`)).data,
  });

  const action = useMutation({
    mutationFn: async ({ key, body }) => {
      const paths = {
        submit: "submit",
        withdraw: "withdraw",
        review: "start-review",
        info: "request-info",
        approve: "approve",
        reject: "reject",
        issue: "issue-policy",
      };
      return (await api.post(`/applications/${id}/${paths[key]}/`, body)).data;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["application", id] });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      toast.push(variables.key === "issue" ? "Policy issued." : "Application updated.", "success");
      setModal(null);
      setNotes("");
      if (variables.key === "issue") navigate(`${basePath}/policies/${data.id}`);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const pay = useMutation({
    mutationFn: async () => (await api.post("/payments/initiate/", {
      application: id,
      method: payMethod,
      phone,
    }, {
      headers: { "Idempotency-Key": crypto.randomUUID?.() || `${id}-${Date.now()}` },
    })).data,
    onSuccess: (data) => {
      const checkoutLink = data.payment?.metadata?.checkout_link;
      if (checkoutLink) {
        window.location.href = checkoutLink;
        return;
      }
      setCreatedPayment(data.payment);
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      queryClient.invalidateQueries({ queryKey: ["application", id] });
      toast.push("Payment initiated.", "success");
      setModal(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (query.isLoading) return <PageLoader />;
  if (query.isError) return <Alert>Could not load this application.</Alert>;
  const app = query.data;
  const role = isDealer ? "dealer" : isProvider ? "provider" : "customer";
  const actions = ACTIONS[role]?.[app.status] || [];

  function run(key) {
    setError("");
    if (key === "pay") {
      setModal("pay");
      return;
    }
    if (key === "issue") {
      setModal("issue");
      return;
    }
    if (["info", "approve", "reject", "withdraw"].includes(key)) {
      setModal(key);
      return;
    }
    action.mutate({ key, body: {} });
  }

  function submitAction(event) {
    event?.preventDefault();
    setError("");
    if (!modal) return;
    if (modal === "issue") {
      action.mutate({ key: "issue", body: issueForm });
      return;
    }
    const body = { notes };
    action.mutate({ key: modal, body });
  }

  return (
    <div>
      <Link to={`${basePath}/applications`} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to applications</Link>
      <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="eyebrow">{app.application_number}</p>
            <StatusBadge status={app.status} />
          </div>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{app.vehicle_summary?.registration_number} · {app.insurer_name}</h1>
          <p className="mt-2 text-sm text-ink-500">{app.product_name} · Quotation {app.quotation_number}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {actions.map((item) => <Button key={item.key} variant={item.tone} onClick={() => run(item.key)}>{item.label}</Button>)}
          {app.policy_id && !isDealer && <Link to={`${isProvider ? "/provider" : "/app"}/policies/${app.policy_id}`}><Button variant="brand" icon={ShieldCheck}>View policy</Button></Link>}
        </div>
      </div>

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}
      {createdPayment && (
        <div className="mb-5">
          <Alert tone={createdPayment.status === "succeeded" ? "success" : "info"} title={`Payment ${createdPayment.reference} · ${titleize(createdPayment.status)}`}>
            {createdPayment.metadata?.instructions || "Your payment is recorded. Await confirmation from the insurer."}
          </Alert>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <div className="surface p-6">
            <h2 className="font-display text-lg font-bold text-ink-950">Application summary</h2>
            <div className="mt-5 grid gap-5 sm:grid-cols-3">
              <DetailItem label="Customer">{app.customer_name}</DetailItem>
              <DetailItem label="Premium">{formatCurrency(app.premium)}</DetailItem>
              <DetailItem label="Sum insured">{formatCurrency(app.sum_insured)}</DetailItem>
              <DetailItem label="Vehicle">{app.vehicle_summary?.registration_number}</DetailItem>
              <DetailItem label="Created">{formatDate(app.created_at)}</DetailItem>
              <DetailItem label="Submitted">{formatDate(app.submitted_at)}</DetailItem>
            </div>
            {app.review_notes && <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900"><strong>Reviewer notes:</strong> {app.review_notes}</div>}
          </div>

          <div className="surface p-6">
            <h2 className="font-display text-lg font-bold text-ink-950">Progress</h2>
            <div className="mt-5 space-y-0">
              {[
                ["Application created", ["draft", "submitted", "under_review", "more_info", "approved", "policy_issued"]],
                ["Submitted to insurer", ["submitted", "under_review", "more_info", "approved", "policy_issued"]],
                ["Insurer decision", ["approved", "policy_issued"]],
                ["Premium verified", ["policy_issued"]],
                ["Policy issued", ["policy_issued"]],
              ].map(([label, reached], index, list) => {
                const done = reached.includes(app.status);
                return (
                  <div key={label} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <span className={`grid h-7 w-7 place-items-center rounded-full text-[10px] font-bold ${done ? "bg-emerald-500 text-white" : "bg-ink-100 text-ink-400"}`}>{done ? <CheckCircle2 className="h-4 w-4" /> : index + 1}</span>
                      {index < list.length - 1 && <span className={`h-9 w-px ${done ? "bg-emerald-200" : "bg-ink-100"}`} />}
                    </div>
                    <p className={`pt-1 text-xs font-semibold ${done ? "text-ink-800" : "text-ink-400"}`}>{label}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6 text-white">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/40">Premium due</p>
            <p className="mt-2 font-display text-3xl font-bold tracking-tight">{formatCurrency(app.premium)}</p>
            <p className="mt-2 text-xs text-white/50">Payment is verified by the insurer before policy issuance.</p>
            {app.status === "approved" && !isDealer && <Button variant="lime" className="mt-5 w-full" icon={CreditCard} onClick={() => run("pay")}>Pay premium</Button>}
          </div>
          <div className="surface p-5">
            <div className="flex items-center gap-2 text-ink-900"><FileText className="h-4 w-4 text-brand-600" /><p className="text-sm font-bold">What happens next?</p></div>
            <ul className="mt-3 space-y-2.5 text-xs leading-relaxed text-ink-500">
              <li>1. The insurer reviews your application and may request more information.</li>
              <li>2. Once approved, pay the premium through M-Pesa or bank transfer.</li>
              <li>3. After payment verification, the insurer issues your policy certificate.</li>
            </ul>
          </div>
        </div>
      </div>

      <Modal
        open={modal === "pay"}
        onClose={() => setModal(null)}
        title="Pay your premium"
        description={`${formatCurrency(app.premium)} for ${app.application_number}`}
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={() => pay.mutate()} loading={pay.isPending}>Initiate payment</Button></>}
      >
        <div className="space-y-4">
          <Select label="Payment method" value={payMethod} onChange={(event) => setPayMethod(event.target.value)} options={PAYMENT_METHODS} />
          {payMethod === "mpesa" && <Input label="M-Pesa phone" required value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="07XX XXX XXX" />}
          <Alert tone="info">
            {payMethod === "mpesa"
              ? "If Daraja is configured, an STK prompt is sent to your phone. Otherwise the payment stays pending for manual reconciliation."
              : payMethod === "card"
                ? "You'll be redirected to a secure checkout page to complete your card payment."
                : "The policy is only issued after authorised provider staff verify the payment reference."}
          </Alert>
        </div>
      </Modal>

      <Modal
        open={Boolean(modal && modal !== "pay" && modal !== "issue")}
        onClose={() => setModal(null)}
        title={{ info: "Request information", approve: "Approve application", reject: "Reject application", withdraw: "Withdraw application" }[modal] || "Update application"}
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button variant={modal === "reject" || modal === "withdraw" ? "danger" : "brand"} onClick={submitAction} loading={action.isPending}>Confirm</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Textarea label={modal === "approve" ? "Notes (optional)" : "Reason / details"} required={modal !== "approve"} value={notes} onChange={(event) => setNotes(event.target.value)} />
          {modal === "approve" && <Alert tone="info">The customer can pay after approval. Do not issue a policy until premium payment is verified.</Alert>}
        </div>
      </Modal>

      <Modal
        open={modal === "issue"}
        onClose={() => setModal(null)}
        title="Issue policy"
        description="Confirm the cover period and provider reference."
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submitAction} loading={action.isPending} icon={ShieldCheck}>Issue policy</Button></>}
      >
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Cover start" type="date" value={issueForm.start_date} onChange={(event) => setIssueForm((current) => ({ ...current, start_date: event.target.value }))} />
            <Input label="Cover end" type="date" value={issueForm.end_date} onChange={(event) => setIssueForm((current) => ({ ...current, end_date: event.target.value }))} />
          </div>
          <Input label="Provider reference" value={issueForm.provider_reference} onChange={(event) => setIssueForm((current) => ({ ...current, provider_reference: event.target.value }))} placeholder="Optional insurer system reference" />
          <Alert tone="warning" icon={ClipboardCheck}>A verified premium payment is required before the policy can be issued.</Alert>
        </div>
      </Modal>
    </div>
  );
}
