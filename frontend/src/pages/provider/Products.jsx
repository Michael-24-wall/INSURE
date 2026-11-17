import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { PRODUCT_CATEGORIES } from "../../lib/constants";
import { formatCurrency, titleize } from "../../lib/format";
import { Alert, Badge, Button, Input, Modal, PageLoader, PageHeader, Select, Textarea } from "../../components/ui";

const emptyProduct = {
  name: "",
  code: "",
  category: "comprehensive",
  description: "",
  base_premium_rate: "5.0000",
  minimum_premium: "5000.00",
  excess_amount: "10000.00",
  min_vehicle_value: "0.00",
  max_vehicle_value: "100000000.00",
  min_vehicle_year: "1990",
  benefits: "",
  exclusions: "",
  terms: "",
  is_active: true,
};

const emptyOption = { name: "", description: "", premium_rate: "0.0000", limit_amount: "0.00", is_default: false };

export default function Products() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState(emptyProduct);
  const [editing, setEditing] = useState(null);
  const [modal, setModal] = useState(null);
  const [selected, setSelected] = useState(null);
  const [optionForm, setOptionForm] = useState(emptyOption);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const orgId = user?.memberships?.[0]?.organization_id;

  const products = useQuery({
    queryKey: ["products", "provider"],
    queryFn: async () => (await api.get("/products/?page_size=200&ordering=-created_at")).data,
  });
  const insurers = useQuery({
    queryKey: ["insurers", "own"],
    queryFn: async () => (await api.get("/insurers/?page_size=100")).data,
    enabled: Boolean(orgId),
  });

  const ownInsurer = useMemo(() => listData(insurers.data).find((insurer) => String(insurer.organization) === String(orgId)) || null, [insurers.data, orgId]);
  const rows = listData(products.data).filter((product) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return [product.name, product.code, product.insurer_name, product.category].join(" ").toLowerCase().includes(term);
  });

  const saveProduct = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        insurer: ownInsurer?.id,
        base_premium_rate: form.base_premium_rate,
        minimum_premium: form.minimum_premium,
        excess_amount: form.excess_amount,
        min_vehicle_value: form.min_vehicle_value,
        max_vehicle_value: form.max_vehicle_value,
        min_vehicle_year: Number(form.min_vehicle_year),
        benefits: form.benefits.split("\n").map((line) => line.trim()).filter(Boolean),
        exclusions: form.exclusions.split("\n").map((line) => line.trim()).filter(Boolean),
      };
      if (editing) {
        delete payload.insurer;
        return (await api.patch(`/products/${editing.id}/`, payload)).data;
      }
      return (await api.post("/products/", payload)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.push(editing ? "Product updated." : "Product created.", "success");
      setModal(null);
      setEditing(null);
      setForm(emptyProduct);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const deleteProduct = useMutation({
    mutationFn: async (product) => api.delete(`/products/${product.id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.push("Product archived.", "success");
      setModal(null);
      setSelected(null);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const addOption = useMutation({
    mutationFn: async () => (await api.post(`/products/${selected.id}/coverage-options/`, optionForm)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.push("Coverage option added.", "success");
      setOptionForm(emptyOption);
      setModal("coverage");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const deleteOption = useMutation({
    mutationFn: async (option) => api.delete(`/products/${selected.id}/coverage-options/${option.id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.push("Coverage option removed.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const coverage = selected ? listData(products.data).find((product) => product.id === selected.id)?.coverage_options || [] : [];

  function openCreate() {
    setError("");
    setEditing(null);
    setForm(emptyProduct);
    setModal("product");
  }

  function openEdit(product) {
    setError("");
    setEditing(product);
    setForm({
      name: product.name,
      code: product.code,
      category: product.category,
      description: product.description || "",
      base_premium_rate: product.base_premium_rate,
      minimum_premium: product.minimum_premium,
      excess_amount: product.excess_amount,
      min_vehicle_value: product.min_vehicle_value,
      max_vehicle_value: product.max_vehicle_value,
      min_vehicle_year: String(product.min_vehicle_year),
      benefits: (product.benefits || []).join("\n"),
      exclusions: (product.exclusions || []).join("\n"),
      terms: product.terms || "",
      is_active: product.is_active,
    });
    setModal("product");
  }

  function submit(event) {
    event.preventDefault();
    setError("");
    if (!editing && !ownInsurer) {
      setError("No insurer profile is linked to your organization. Ask an administrator to verify your organization.");
      return;
    }
    saveProduct.mutate();
  }

  function submitOption(event) {
    event.preventDefault();
    setError("");
    addOption.mutate();
  }

  if (products.isLoading) return <PageLoader />;
  if (products.isError) {
    return <div className="surface p-5"><Alert title="We couldn't load your products">Please check your connection and try again.</Alert></div>;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Underwriting catalogue"
        title="Insurance products"
        description="Define the motor products your organization sells, including rates, eligibility and optional covers."
        actions={<Button icon={Plus} onClick={openCreate}>New product</Button>}
      />

      {error && <div className="mb-5"><Alert>{error}</Alert></div>}

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-ink-500">{rows.length} product{rows.length === 1 ? "" : "s"}{ownInsurer ? ` · ${ownInsurer.display_name}` : ""}</p>
        <Input placeholder="Search products" value={search} onChange={(event) => setSearch(event.target.value)} className="w-full sm:w-72" />
      </div>

      {rows.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((product) => (
            <div key={product.id} className="surface flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700"><Layers className="h-5 w-5" /></span>
                <div className="flex items-center gap-2">
                  <Badge tone={product.is_active ? "green" : "gray"}>{product.is_active ? "Active" : "Inactive"}</Badge>
                  <button onClick={() => openEdit(product)} className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-50 hover:text-ink-900" aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></button>
                  <button onClick={() => { setSelected(product); setError(""); setModal("delete"); }} className="rounded-lg p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600" aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              </div>
              <p className="mt-4 font-display text-base font-bold text-ink-950">{product.name}</p>
              <p className="mt-1 text-xs text-ink-400">{product.code} · {titleize(product.category)}</p>
              <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-ink-500">{product.description || "No description."}</p>
              <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-ink-50 p-3">
                <div><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Rate</p><p className="mt-1 text-xs font-bold text-ink-900">{Number(product.base_premium_rate).toFixed(2)}%</p></div>
                <div><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Min premium</p><p className="mt-1 text-xs font-bold text-ink-900">{formatCurrency(product.minimum_premium)}</p></div>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-[11px] text-ink-400">{product.coverage_options?.length || 0} coverage options</span>
                <button onClick={() => { setSelected(product); setError(""); setOptionForm(emptyOption); setModal("coverage"); }} className="text-xs font-bold text-brand-700 hover:underline">Manage covers</button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="surface p-12 text-center">
          <ShieldCheck className="mx-auto h-9 w-9 text-ink-300" />
          <p className="mt-3 text-sm font-bold text-ink-800">No products yet</p>
          <p className="mt-1 text-xs text-ink-400">Publish products across the insurance lines your organisation is licensed to offer.</p>
          <Button className="mt-4" icon={Plus} onClick={openCreate}>New product</Button>
        </div>
      )}

      <Modal
        open={modal === "product"}
        onClose={() => setModal(null)}
        title={editing ? "Edit product" : "New product"}
        wide
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button onClick={submit} loading={saveProduct.isPending}>{editing ? "Save changes" : "Create product"}</Button></>}
      >
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Product name" required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
            <Input label="Product code" required value={form.code} onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))} placeholder="e.g. COMP-01" />
          </div>
          <Select label="Category" value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} options={PRODUCT_CATEGORIES.map((category) => ({ value: category.value || category, label: category.label || titleize(category.value || category) }))} />
          <Textarea label="Description" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Input label="Base rate (%)" type="number" step="0.0001" required value={form.base_premium_rate} onChange={(event) => setForm((current) => ({ ...current, base_premium_rate: event.target.value }))} />
            <Input label="Minimum premium" type="number" step="0.01" required value={form.minimum_premium} onChange={(event) => setForm((current) => ({ ...current, minimum_premium: event.target.value }))} />
            <Input label="Excess amount" type="number" step="0.01" required value={form.excess_amount} onChange={(event) => setForm((current) => ({ ...current, excess_amount: event.target.value }))} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Input label="Min vehicle value" type="number" step="0.01" value={form.min_vehicle_value} onChange={(event) => setForm((current) => ({ ...current, min_vehicle_value: event.target.value }))} />
            <Input label="Max vehicle value" type="number" step="0.01" value={form.max_vehicle_value} onChange={(event) => setForm((current) => ({ ...current, max_vehicle_value: event.target.value }))} />
            <Input label="Min vehicle year" type="number" value={form.min_vehicle_year} onChange={(event) => setForm((current) => ({ ...current, min_vehicle_year: event.target.value }))} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Textarea label="Benefits (one per line)" value={form.benefits} onChange={(event) => setForm((current) => ({ ...current, benefits: event.target.value }))} />
            <Textarea label="Exclusions (one per line)" value={form.exclusions} onChange={(event) => setForm((current) => ({ ...current, exclusions: event.target.value }))} />
          </div>
          <Textarea label="Terms" value={form.terms} onChange={(event) => setForm((current) => ({ ...current, terms: event.target.value }))} />
          <label className="flex items-center gap-2 text-sm text-ink-700"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} className="h-4 w-4 rounded border-ink-300 text-brand-600" /> Available for quoting</label>
        </form>
      </Modal>

      <Modal
        open={modal === "coverage"}
        onClose={() => setModal(null)}
        title={`Coverage options · ${selected?.name || ""}`}
        description="Optional add-ons customers can select with this product."
        wide
        footer={<Button variant="secondary" onClick={() => setModal(null)}>Done</Button>}
      >
        <div className="space-y-5">
          {error && <Alert>{error}</Alert>}
          <div className="surface divide-y divide-ink-100">
            {coverage.length ? coverage.map((option) => (
              <div key={option.id} className="flex items-center justify-between gap-3 p-3">
                <div>
                  <p className="text-xs font-bold text-ink-900">{option.name} {option.is_default && <Badge tone="brand">Default</Badge>}</p>
                  <p className="mt-0.5 text-[10px] text-ink-400">{option.description || "No description"} · {Number(option.premium_rate).toFixed(2)}% · limit {formatCurrency(option.limit_amount)}</p>
                </div>
                <button onClick={() => deleteOption.mutate(option)} className="rounded-lg p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600" aria-label="Remove option"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            )) : <p className="p-4 text-xs text-ink-400">No coverage options yet.</p>}
          </div>
          <form onSubmit={submitOption} className="rounded-2xl border border-ink-100 p-4">
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-ink-500">Add coverage option</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Name" required value={optionForm.name} onChange={(event) => setOptionForm((current) => ({ ...current, name: event.target.value }))} />
              <Input label="Description" value={optionForm.description} onChange={(event) => setOptionForm((current) => ({ ...current, description: event.target.value }))} />
              <Input label="Premium rate (%)" type="number" step="0.0001" value={optionForm.premium_rate} onChange={(event) => setOptionForm((current) => ({ ...current, premium_rate: event.target.value }))} />
              <Input label="Limit amount" type="number" step="0.01" value={optionForm.limit_amount} onChange={(event) => setOptionForm((current) => ({ ...current, limit_amount: event.target.value }))} />
            </div>
            <div className="mt-3 flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-ink-600"><input type="checkbox" checked={optionForm.is_default} onChange={(event) => setOptionForm((current) => ({ ...current, is_default: event.target.checked }))} className="h-4 w-4 rounded border-ink-300 text-brand-600" /> Selected by default</label>
              <Button type="submit" size="sm" icon={Plus} loading={addOption.isPending}>Add option</Button>
            </div>
          </form>
        </div>
      </Modal>

      <Modal
        open={modal === "delete"}
        onClose={() => setModal(null)}
        title="Archive product"
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button variant="danger" onClick={() => deleteProduct.mutate(selected)} loading={deleteProduct.isPending}>Archive product</Button></>}
      >
        <p className="text-sm text-ink-600">Archive <strong>{selected?.name}</strong>? Existing quotations and policies are not affected, but the product will no longer be offered.</p>
      </Modal>
    </div>
  );
}
