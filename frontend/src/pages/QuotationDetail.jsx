import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Clock3, FileText, MessageSquare, Pencil, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import api, { getErrorMessage, listData } from "../api/client";
import { formatCurrency, formatDate, titleize } from "../lib/format";
import { Alert, Button, Input, Modal, PageLoader, Select, StatusBadge, Textarea } from "../components/ui";
import { DetailItem } from "../components/DataTable";
import { useToast } from "../context/ToastContext";

const EMPTY_FORM = {
  productId: "",
  premium: "",
  taxes: "0",
  fees: "0",
  otherCharges: "0",
  excess: "",
  benefits: "",
  exclusions: "",
  coverageLimits: "",
  deductibles: "",
  terms: "",
  notes: "",
  validUntil: "",
};

function parsePairs(text) {
  return Object.fromEntries(
    text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const index = line.indexOf(":");
        return index === -1
          ? [line, ""]
          : [line.slice(0, index).trim(), line.slice(index + 1).trim()];
      })
  );
}

function pairsToText(value) {
  return Object.entries(value || {}).map(([key, item]) => `${key}: ${item}`).join("\n");
}

function toIsoDate(value) {
  return value ? new Date(`${value}T23:59:59`).toISOString() : null;
}

export default function QuotationDetail() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const isProvider = location.pathname.startsWith("/provider");
  const isDealer = location.pathname.startsWith("/dealer");
  const basePath = isProvider ? "/provider/quotes" : isDealer ? "/dealer/quotes" : "/app/quotes";
  const [error, setError] = useState("");
  const [responding, setResponding] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [workingId, setWorkingId] = useState(null);
  const [requestAction, setRequestAction] = useState(null);
  const [requestNotes, setRequestNotes] = useState("");
  const [quoteAction, setQuoteAction] = useState(null);
  const [quoteNotes, setQuoteNotes] = useState("");
  const [clarifying, setClarifying] = useState(false);
  const [clarifyNote, setClarifyNote] = useState("");

  const request = useQuery({
    queryKey: ["quotation-request", id],
    queryFn: async () => (await api.get(`/quotation-requests/${id}/`)).data,
  });
  const quotes = useQuery({
    queryKey: ["quotations", "request", id],
    queryFn: async () => (await api.get(`/quotations/?request=${id}&page_size=100&ordering=premium`)).data,
  });
  const products = useQuery({
    queryKey: ["products", "respond", request.data?.coverage_type],
    queryFn: async () => (await api.get(`/products/?page_size=100&is_active=true&category=${request.data?.coverage_type}`)).data,
    enabled: isProvider && Boolean(request.data),
  });

  const quoteRows = useMemo(() => listData(quotes.data), [quotes.data]);
  const matchingProducts = listData(products.data);
  const req = request.data;
  const totalPreview = ["premium", "taxes", "fees", "otherCharges"].reduce(
    (sum, key) => sum + (Number(form[key]) || 0),
    0
  );

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["quotations"] });
    queryClient.invalidateQueries({ queryKey: ["quotation-request", id] });
    queryClient.invalidateQueries({ queryKey: ["quotation-requests"] });
    queryClient.invalidateQueries({ queryKey: ["applications"] });
  }

  const select = useMutation({
    mutationFn: async (quote) => {
      setWorkingId(quote.id);
      if (quote.application_id) return { id: quote.application_id };
      await api.post(`/quotations/${quote.id}/select/`);
      const endpoint = isDealer ? "/applications/dealer-create/" : "/applications/";
      const { data } = await api.post(endpoint, { quotation: quote.id });
      return data;
    },
    onSuccess: (application) => {
      refresh();
      toast.push("Quotation selected and application started.", "success");
      navigate(`${isDealer ? "/dealer" : "/app"}/applications/${application.id}`);
    },
    onError: (err) => setError(getErrorMessage(err)),
    onSettled: () => setWorkingId(null),
  });

  const respond = useMutation({
    mutationFn: async () => {
      const body = {
        premium: Number(form.premium),
        taxes: Number(form.taxes || 0),
        fees: Number(form.fees || 0),
        other_charges: Number(form.otherCharges || 0),
        excess_amount: Number(form.excess),
        notes: form.notes,
        benefits: form.benefits ? form.benefits.split("\n").map((line) => line.trim()).filter(Boolean) : undefined,
        exclusions: form.exclusions ? form.exclusions.split("\n").map((line) => line.trim()).filter(Boolean) : undefined,
        coverage_limits: parsePairs(form.coverageLimits),
        deductibles: parsePairs(form.deductibles),
        terms: form.terms,
      };
      const expiry = toIsoDate(form.validUntil);
      if (editing) {
        if (expiry) body.valid_until = expiry;
        return (await api.patch(`/quotations/${editing.id}/`, body)).data;
      }
      return (await api.post("/quotations/", {
        ...body,
        request: id,
        product: form.productId,
        valid_days: 14,
        ...(expiry ? { expires_at: expiry } : {}),
      })).data;
    },
    onSuccess: () => {
      refresh();
      toast.push(editing ? "Quotation updated." : "Quotation submitted.", "success");
      closeRespond();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const requestActionMutation = useMutation({
    mutationFn: async () => {
      const body = requestAction === "start-review" ? {} : { notes: requestNotes };
      return (await api.post(`/quotation-requests/${id}/${requestAction}/`, body)).data;
    },
    onSuccess: () => {
      refresh();
      toast.push(requestAction === "reject" ? "Request declined." : "Request updated.", "success");
      setRequestAction(null);
      setRequestNotes("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const quoteActionMutation = useMutation({
    mutationFn: async () => (await api.post(`/quotations/${quoteAction.quote.id}/${quoteAction.type}/`, { notes: quoteNotes })).data,
    onSuccess: () => {
      refresh();
      toast.push(quoteAction.type === "reject" ? "Quotation declined." : "Information requested.", "success");
      setQuoteAction(null);
      setQuoteNotes("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const clarify = useMutation({
    mutationFn: async () => (await api.post(`/quotation-requests/${id}/clarify/`, { notes: clarifyNote })).data,
    onSuccess: () => {
      refresh();
      toast.push("Clarification sent to the insurer.", "success");
      setClarifying(false);
      setClarifyNote("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  if (request.isLoading) return <PageLoader />;
  if (request.isError) return <Alert>Could not load this quotation request.</Alert>;

  function resetForm() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError("");
  }

  function closeRespond() {
    setResponding(false);
    resetForm();
  }

  function openCreate() {
    resetForm();
    setResponding(true);
  }

  function openEdit(quote) {
    setEditing(quote);
    setForm({
      productId: quote.product,
      premium: String(quote.premium ?? ""),
      taxes: String(quote.taxes ?? "0"),
      fees: String(quote.fees ?? "0"),
      otherCharges: String(quote.other_charges ?? "0"),
      excess: String(quote.excess_amount ?? ""),
      benefits: (quote.benefits || []).join("\n"),
      exclusions: (quote.exclusions || []).join("\n"),
      coverageLimits: pairsToText(quote.coverage_limits),
      deductibles: pairsToText(quote.deductibles),
      terms: quote.terms || "",
      notes: quote.notes || "",
      validUntil: quote.valid_until ? String(quote.valid_until).slice(0, 10) : "",
    });
    setError("");
    setResponding(true);
  }

  function submitResponse(event) {
    event.preventDefault();
    setError("");
    respond.mutate();
  }

  function runRequestAction(action) {
    setError("");
    if (action === "start-review") {
      requestActionMutation.mutate();
      return;
    }
    setRequestAction(action);
  }

  function submitRequestAction(event) {
    event.preventDefault();
    setError("");
    requestActionMutation.mutate();
  }

  function submitQuoteAction(event) {
    event.preventDefault();
    setError("");
    quoteActionMutation.mutate();
  }

  const canReviewRequest = isProvider && req.insurer && !["converted", "cancelled", "expired", "rejected", "selected"].includes(req.status);
  const canSelect = !isProvider && req.status !== "converted";

  return (
    <div>
      <Link to={basePath} className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to quotations</Link>
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">{req.request_number}</p>
            <StatusBadge status={req.status} />
            {req.insurer_name && <span className="text-[10px] font-bold uppercase tracking-wide text-ink-400">Directed to {req.insurer_name}</span>}
          </div>
          <h1 className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{titleize(req.coverage_type)} cover</h1>
          <p className="mt-2 text-sm text-ink-500">{req.vehicle_summary?.registration_number} · {req.vehicle_summary?.make} {req.vehicle_summary?.model} · {req.vehicle_summary?.year}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canReviewRequest && ["pending", "more_info", "under_review", "quoted"].includes(req.status) && (
            <>
              <Button variant="secondary" onClick={() => runRequestAction("start-review")} loading={requestActionMutation.isPending && !requestAction}>Start review</Button>
              <Button variant="secondary" icon={MessageSquare} onClick={() => runRequestAction("request-info")}>Request info</Button>
              <Button variant="danger-soft" icon={XCircle} onClick={() => runRequestAction("reject")}>Decline</Button>
            </>
          )}
          {isProvider && ["pending", "more_info", "under_review", "quoted"].includes(req.status) && (
            <Button icon={Sparkles} onClick={openCreate}>Submit a quotation</Button>
          )}
        </div>
      </div>

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}

      <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
        <div className="space-y-4">
          <div className="surface p-5">
            <h2 className="font-display text-base font-bold text-ink-950">Request details</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              <DetailItem label="Customer">{req.customer_name}</DetailItem>
              {req.dealership_name && <DetailItem label="Dealership">{req.dealership_name}</DetailItem>}
              <DetailItem label="Sum insured">{formatCurrency(req.sum_insured)}</DetailItem>
              <DetailItem label="Desired start">{formatDate(req.desired_start_date)}</DetailItem>
              <DetailItem label="Expires">{formatDate(req.expires_at)}</DetailItem>
              <DetailItem label="Quotes received">{req.quotation_count}</DetailItem>
            </div>
            {req.notes && <div className="mt-4 rounded-xl bg-ink-50 p-3 text-xs leading-relaxed text-ink-600">{req.notes}</div>}
            {req.insurer_notes && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-900">
                <strong>Insurer note:</strong> {req.insurer_notes}
              </div>
            )}
            {req.clarification_note && (
              <div className="mt-4 rounded-xl border border-brand-200 bg-brand-50 p-3 text-xs leading-relaxed text-brand-900">
                <strong>Clarification requested:</strong> {req.clarification_note}
              </div>
            )}
            {!isProvider && !["converted", "selected", "rejected", "expired", "cancelled"].includes(req.status) && (
              <Button size="sm" variant="secondary" className="mt-4" icon={MessageSquare} onClick={() => { setError(""); setClarifying(true); }}>Request clarification</Button>
            )}
          </div>
          <div className="rounded-3xl bg-ink-950 p-5 text-white">
            <ShieldCheck className="h-6 w-6 text-lime-300" />
            <p className="mt-4 text-sm font-bold">Compare before you decide</p>
            <p className="mt-1.5 text-xs leading-relaxed text-white/55">Check premium, total payable, excess, limits, benefits and exclusions together. The lowest premium is not always the best value.</p>
          </div>
        </div>

        <div>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-display text-lg font-bold text-ink-950">Quotations</h2>
              <p className="text-xs text-ink-400">{quoteRows.length} offer{quoteRows.length === 1 ? "" : "s"} received</p>
            </div>
          </div>
          <div className="space-y-3">
            {quoteRows.map((quote) => (
              <div key={quote.id} className={`surface overflow-hidden p-5 ${quote.status === "selected" ? "ring-2 ring-brand-500" : ""}`}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 font-display text-sm font-bold text-brand-700">{quote.insurer_name?.slice(0, 2).toUpperCase()}</span>
                    <div>
                      <p className="font-display text-base font-bold text-ink-950">{quote.insurer_name}</p>
                      <p className="text-xs text-ink-400">{quote.product_name} · {titleize(quote.product_category)}</p>
                      <p className="mt-1 text-[10px] text-ink-300">{quote.quotation_number}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">Premium</p>
                    <p className="font-display text-2xl font-bold tracking-tight text-ink-950">{formatCurrency(quote.premium)}</p>
                    <p className="text-[10px] text-ink-400">Excess {formatCurrency(quote.excess_amount)}</p>
                    {Number(quote.total_payable) !== Number(quote.premium) && (
                      <p className="mt-1 text-[11px] font-bold text-brand-700">Total {formatCurrency(quote.total_payable)}</p>
                    )}
                  </div>
                </div>

                {(Number(quote.taxes) > 0 || Number(quote.fees) > 0 || Number(quote.other_charges) > 0) && (
                  <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-ink-50 p-3 text-[11px] text-ink-600 sm:grid-cols-4">
                    <span>Taxes <strong className="text-ink-900">{formatCurrency(quote.taxes)}</strong></span>
                    <span>Fees <strong className="text-ink-900">{formatCurrency(quote.fees)}</strong></span>
                    <span>Other <strong className="text-ink-900">{formatCurrency(quote.other_charges)}</strong></span>
                    <span>Total <strong className="text-brand-700">{formatCurrency(quote.total_payable)}</strong></span>
                  </div>
                )}

                {quote.benefits?.length > 0 && (
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {quote.benefits.slice(0, 4).map((benefit) => (
                      <p key={benefit} className="flex items-start gap-1.5 text-xs text-ink-600"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />{benefit}</p>
                    ))}
                  </div>
                )}

                {quote.coverage_limits && Object.keys(quote.coverage_limits).length > 0 && (
                  <div className="mt-3 rounded-xl border border-ink-100 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-ink-400">Coverage limits</p>
                    <div className="mt-2 grid gap-1.5 text-[11px] text-ink-600 sm:grid-cols-2">
                      {Object.entries(quote.coverage_limits).map(([key, value]) => (
                        <p key={key}><span className="font-semibold text-ink-800">{key}:</span> {value}</p>
                      ))}
                    </div>
                  </div>
                )}

                {quote.deductibles && Object.keys(quote.deductibles).length > 0 && (
                  <div className="mt-3 rounded-xl border border-ink-100 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-ink-400">Deductibles</p>
                    <div className="mt-2 grid gap-1.5 text-[11px] text-ink-600 sm:grid-cols-2">
                      {Object.entries(quote.deductibles).map(([key, value]) => (
                        <p key={key}><span className="font-semibold text-ink-800">{key}:</span> {value}</p>
                      ))}
                    </div>
                  </div>
                )}

                {quote.terms && <p className="mt-3 text-[11px] leading-relaxed text-ink-500">{quote.terms}</p>}
                {quote.notes && <p className="mt-2 text-[11px] leading-relaxed text-ink-500">{quote.notes}</p>}

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 pt-4">
                  <div className="flex items-center gap-3 text-[11px] text-ink-400">
                    <span className="flex items-center gap-1"><Clock3 className="h-3 w-3" /> valid until {formatDate(quote.valid_until)}</span>
                    <StatusBadge status={quote.status} />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {isProvider && ["received", "more_info"].includes(quote.status) && (
                      <>
                        <Button size="sm" variant="secondary" icon={Pencil} onClick={() => openEdit(quote)}>Edit offer</Button>
                        <Button size="sm" variant="secondary" icon={MessageSquare} onClick={() => { setError(""); setQuoteNotes(""); setQuoteAction({ type: "request-info", quote }); }}>Request info</Button>
                        <Button size="sm" variant="danger-soft" onClick={() => { setError(""); setQuoteNotes(""); setQuoteAction({ type: "reject", quote }); }}>Decline</Button>
                      </>
                    )}
                    {canSelect && ["received", "selected"].includes(quote.status) && (
                      <Button size="sm" variant={quote.status === "selected" ? "secondary" : "brand"} disabled={workingId === quote.id} loading={workingId === quote.id} onClick={() => select.mutate(quote)}>
                        {quote.status === "selected" ? "Continue application" : "Select offer"} <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {quote.status === "selected" && <span className="flex items-center gap-1 text-xs font-bold text-emerald-700"><Check className="h-4 w-4" /> Selected</span>}
                  </div>
                </div>
              </div>
            ))}
            {!quoteRows.length && (
              <div className="surface p-10 text-center">
                <FileText className="mx-auto h-8 w-8 text-ink-300" />
                <p className="mt-3 text-sm font-bold text-ink-800">No quotes received yet</p>
                <p className="mt-1 text-xs text-ink-400">{isProvider ? "Be the first to respond to this request." : "The insurer is reviewing this request. Check back shortly."}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal
        open={responding}
        onClose={closeRespond}
        title={editing ? "Prepare quotation" : "Submit a quotation"}
        description={`${req.request_number} · ${titleize(req.coverage_type)}`}
        size="lg"
        footer={<><Button variant="secondary" onClick={closeRespond}>Cancel</Button><Button onClick={submitResponse} loading={respond.isPending}>{editing ? "Save offer" : "Submit quotation"}</Button></>}
      >
        <form onSubmit={submitResponse} className="space-y-4">
          <Select
            label="Product"
            required
            disabled={Boolean(editing)}
            placeholder="Select a matching product"
            value={form.productId}
            onChange={(event) => {
              const product = matchingProducts.find((p) => String(p.id) === event.target.value);
              setForm((current) => ({
                ...current,
                productId: event.target.value,
                ...(product && !current.premium
                  ? {
                      premium: (Number(req.sum_insured) * Number(product.base_premium_rate) / 100).toFixed(2),
                      excess: String(product.excess_amount || ""),
                      benefits: (product.benefits || []).join("\n"),
                      exclusions: (product.exclusions || []).join("\n"),
                      terms: product.terms || "",
                    }
                  : {}),
              }));
            }}
            options={matchingProducts.map((product) => ({ value: product.id, label: `${product.name} · from ${formatCurrency(product.minimum_premium)}` }))}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Premium (KES)" type="number" min="0.01" step="0.01" required value={form.premium} onChange={(event) => setForm((current) => ({ ...current, premium: event.target.value }))} />
            <Input label="Excess (KES)" type="number" min="0" step="0.01" required value={form.excess} onChange={(event) => setForm((current) => ({ ...current, excess: event.target.value }))} />
            <Input label="Taxes (KES)" type="number" min="0" step="0.01" value={form.taxes} onChange={(event) => setForm((current) => ({ ...current, taxes: event.target.value }))} />
            <Input label="Fees (KES)" type="number" min="0" step="0.01" value={form.fees} onChange={(event) => setForm((current) => ({ ...current, fees: event.target.value }))} />
            <Input label="Other charges (KES)" type="number" min="0" step="0.01" value={form.otherCharges} onChange={(event) => setForm((current) => ({ ...current, otherCharges: event.target.value }))} />
            <Input label="Quote valid until" type="date" value={form.validUntil} onChange={(event) => setForm((current) => ({ ...current, validUntil: event.target.value }))} />
          </div>
          <div className="rounded-xl bg-brand-50 px-4 py-3 text-sm font-bold text-brand-800">Total payable: {formatCurrency(totalPreview)}</div>
          <Textarea label="Benefits (one per line)" value={form.benefits} onChange={(event) => setForm((current) => ({ ...current, benefits: event.target.value }))} placeholder={"Own damage cover\nThird-party liability\nWindscreen cover"} />
          <Textarea label="Exclusions (one per line)" value={form.exclusions} onChange={(event) => setForm((current) => ({ ...current, exclusions: event.target.value }))} placeholder="Optional" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Textarea label="Coverage limits (one per line)" value={form.coverageLimits} onChange={(event) => setForm((current) => ({ ...current, coverageLimits: event.target.value }))} placeholder={"Own damage: 2000000\nThird party: 1000000"} />
            <Textarea label="Deductibles (one per line)" value={form.deductibles} onChange={(event) => setForm((current) => ({ ...current, deductibles: event.target.value }))} placeholder={"Own damage: 15000"} />
          </div>
          <Textarea label="Terms" value={form.terms} onChange={(event) => setForm((current) => ({ ...current, terms: event.target.value }))} placeholder="Key terms and conditions for this offer" />
          <Textarea label="Notes" value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Optional context for the customer" />
          {!matchingProducts.length && !editing && <Alert tone="warning">No active products match the requested cover type. Add a product first.</Alert>}
        </form>
      </Modal>

      <Modal
        open={Boolean(requestAction)}
        onClose={() => { setRequestAction(null); setRequestNotes(""); }}
        title={requestAction === "reject" ? "Decline request" : "Request information"}
        footer={<><Button variant="secondary" onClick={() => { setRequestAction(null); setRequestNotes(""); }}>Cancel</Button><Button variant={requestAction === "reject" ? "danger" : "brand"} onClick={submitRequestAction} loading={requestActionMutation.isPending}>Confirm</Button></>}
      >
        <form onSubmit={submitRequestAction} className="space-y-4">
          <Textarea label={requestAction === "reject" ? "Reason for declining" : "Information required"} required value={requestNotes} onChange={(event) => setRequestNotes(event.target.value)} />
        </form>
      </Modal>

      <Modal
        open={Boolean(quoteAction)}
        onClose={() => { setQuoteAction(null); setQuoteNotes(""); }}
        title={quoteAction?.type === "reject" ? "Decline quotation" : "Request information"}
        description={quoteAction ? `${quoteAction.quote.quotation_number} · ${quoteAction.quote.product_name}` : ""}
        footer={<><Button variant="secondary" onClick={() => { setQuoteAction(null); setQuoteNotes(""); }}>Cancel</Button><Button variant={quoteAction?.type === "reject" ? "danger" : "brand"} onClick={submitQuoteAction} loading={quoteActionMutation.isPending}>Confirm</Button></>}
      >
        <form onSubmit={submitQuoteAction} className="space-y-4">
          <Textarea label={quoteAction?.type === "reject" ? "Reason for declining" : "Information required"} required value={quoteNotes} onChange={(event) => setQuoteNotes(event.target.value)} />
        </form>
      </Modal>

      <Modal
        open={clarifying}
        onClose={() => { setClarifying(false); setClarifyNote(""); }}
        title="Request clarification"
        description={`${req.request_number} · ${req.insurer_name || "Insurer"}`}
        footer={<><Button variant="secondary" onClick={() => { setClarifying(false); setClarifyNote(""); }}>Cancel</Button><Button onClick={() => clarify.mutate()} loading={clarify.isPending}>Send</Button></>}
      >
        <Textarea label="What do you need clarified?" required value={clarifyNote} onChange={(event) => setClarifyNote(event.target.value)} />
      </Modal>
    </div>
  );
}
