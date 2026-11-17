import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Building2, Car, FileSearch, FileText, Handshake, ImagePlus, Network, Star, Trash2 } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, titleize } from "../../lib/format";
import { DashboardHero } from "../../components/Hero";
import { Alert, Button, Input, Modal, PageLoader, SearchInput, Select, Stat, StatusBadge, Tabs, Textarea } from "../../components/ui";

function PartnerCard({ insurer, onRequest }) {
  return (
    <div className="surface flex flex-col gap-3 p-5">
      <div className="flex items-center gap-3">
        {insurer.logo ? (
          <img src={insurer.logo} alt={insurer.display_name} className="h-12 w-12 rounded-xl object-cover" />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-navy-500 text-white"><Building2 className="h-6 w-6" /></span>
        )}
        <div>
          <p className="font-display text-sm font-bold text-ink-950">{insurer.display_name}</p>
          <p className="text-[11px] text-ink-500">{insurer.county || insurer.country} · {insurer.product_count} products</p>
        </div>
      </div>
      <p className="line-clamp-2 text-xs text-ink-500">{insurer.description}</p>
      <div className="mt-auto flex items-center justify-between">
        <StatusBadge status={insurer.status} />
        {insurer.partnership_status === "none" ? (
          <Button size="sm" variant="brand" onClick={() => onRequest(insurer)}>Request partnership</Button>
        ) : (
          <span className="text-xs font-semibold text-brand-700">{titleize(insurer.partnership_status)}</span>
        )}
      </div>
    </div>
  );
}

export default function DealerDashboard() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("network");
  const [requestInsurer, setRequestInsurer] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [vehicleForm, setVehicleForm] = useState({ make: "", model: "", year: "", asking_price: "", condition: "used", transmission: "automatic", fuel_type: "petrol", category: "saloon", description: "" });
  const [photoVehicleId, setPhotoVehicleId] = useState(null);
  const [photoFile, setPhotoFile] = useState(null);
  const [photoPrimary, setPhotoPrimary] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [quoteVehicleId, setQuoteVehicleId] = useState(null);
  const [quoteForm, setQuoteForm] = useState({ insurer: "", customer: "", coverage_type: "comprehensive", sum_insured: "", desired_start_date: "", notes: "" });
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerQuery, setCustomerQuery] = useState("");
  const [quoteError, setQuoteError] = useState("");
  const orgId = user?.memberships?.find((m) => m.organization_type === "dealer")?.organization_id;

  const insurers = useQuery({ queryKey: ["network-insurers"], queryFn: async () => (await api.get("/business-network/insurers/?page_size=100")).data });
  const partnerships = useQuery({ queryKey: ["partnerships"], queryFn: async () => (await api.get("/business-network/partnerships/?page_size=100")).data });
  const requests = useQuery({ queryKey: ["partnership-requests"], queryFn: async () => (await api.get("/business-network/partnership-requests/?page_size=100")).data });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: async () => (await api.get("/business-network/inventory/?page_size=100")).data });
  const customerMatches = useQuery({
    queryKey: ["dealer-customers", customerQuery],
    queryFn: async () => (await api.get("/business-network/dealer/customers/", { params: { search: customerQuery.trim() } })).data,
    enabled: customerQuery.trim().length >= 2,
  });

  const sendRequest = useMutation({
    mutationFn: async () => (await api.post("/business-network/partnership-requests/", { from_organization: orgId, to_organization: requestInsurer.organization_id, message })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partnership-requests"] });
      queryClient.invalidateQueries({ queryKey: ["network-insurers"] });
      toast.push("Partnership request sent.", "success");
      setRequestInsurer(null); setMessage("");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const respond = useMutation({
    mutationFn: async ({ id, action, note }) => (await api.post(`/business-network/partnership-requests/${id}/respond/`, { action, note })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partnership-requests"] });
      queryClient.invalidateQueries({ queryKey: ["partnerships"] });
      toast.push("Request updated.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const suspendPartnership = useMutation({
    mutationFn: async ({ id, reason }) => (await api.post(`/business-network/partnerships/${id}/suspend/`, { reason })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["partnerships"] });
      toast.push("Partnership suspended.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const addVehicle = useMutation({
    mutationFn: async () => (await api.post("/business-network/inventory/", { ...vehicleForm, dealership: orgId })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      toast.push("Vehicle added to inventory.", "success");
      setVehicleForm({ make: "", model: "", year: "", asking_price: "", condition: "used", transmission: "automatic", fuel_type: "petrol", category: "saloon", description: "" });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const markSold = useMutation({
    mutationFn: async (id) => (await api.post(`/business-network/inventory/${id}/mark-sold/`)).data,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["inventory"] }); toast.push("Marked as sold.", "success"); },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const uploadPhoto = useMutation({
    mutationFn: async ({ vehicleId, file, isPrimary }) => {
      const body = new FormData();
      body.append("image", file);
      if (isPrimary) body.append("is_primary", "true");
      return (await api.post(`/business-network/inventory/${vehicleId}/photos/`, body, { headers: { "Content-Type": "multipart/form-data" } })).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      toast.push("Photo uploaded.", "success");
      setPhotoFile(null);
      setPhotoPrimary(false);
      setPhotoError("");
    },
    onError: (err) => setPhotoError(getErrorMessage(err)),
  });

  const deletePhoto = useMutation({
    mutationFn: async ({ vehicleId, photoId }) => (await api.delete(`/business-network/inventory/${vehicleId}/photos/${photoId}/`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      toast.push("Photo removed.", "success");
    },
    onError: (err) => setPhotoError(getErrorMessage(err)),
  });

  const openPhotoModal = (vehicleId) => {
    setPhotoVehicleId(vehicleId);
    setPhotoFile(null);
    setPhotoPrimary(false);
    setPhotoError("");
  };

  const closePhotoModal = () => {
    setPhotoVehicleId(null);
    setPhotoFile(null);
    setPhotoPrimary(false);
    setPhotoError("");
  };

  const openQuoteModal = (vehicle) => {
    setQuoteVehicleId(vehicle.id);
    setQuoteForm({
      insurer: "",
      customer: "",
      coverage_type: "comprehensive",
      sum_insured: String(Math.round(Number(vehicle.asking_price || 0))),
      desired_start_date: new Date().toISOString().slice(0, 10),
      notes: "",
    });
    setSelectedCustomer(null);
    setCustomerQuery("");
    setQuoteError("");
  };

  const closeQuoteModal = () => {
    setQuoteVehicleId(null);
    setSelectedCustomer(null);
    setCustomerQuery("");
    setQuoteError("");
  };

  const requestQuote = useMutation({
    mutationFn: async () => (await api.post("/business-network/dealer/quotations/", { inventory_vehicle: quoteVehicleId, ...quoteForm })).data,
    onSuccess: (data) => {
      toast.push(`Quotation request ${data.request?.request_number || "submitted"}.`, "success");
      closeQuoteModal();
    },
    onError: (err) => setQuoteError(getErrorMessage(err)),
  });

  if (insurers.isLoading || partnerships.isLoading || requests.isLoading || inventory.isLoading) return <PageLoader />;
  if (insurers.isError || partnerships.isError || requests.isError || inventory.isError) {
    return (
      <div className="surface p-5">
        <Alert title="We couldn't load your dealership workspace.">Please refresh the page to try again.</Alert>
      </div>
    );
  }

  const insurerRows = listData(insurers.data);
  const partnerRows = listData(partnerships.data);
  const requestRows = listData(requests.data);
  const inventoryRows = listData(inventory.data);
  const photoVehicle = inventoryRows.find((v) => v.id === photoVehicleId);
  const quoteVehicle = inventoryRows.find((v) => v.id === quoteVehicleId);
  const activePartners = partnerRows.filter((p) => p.status === "active");
  const customerResults = listData(customerMatches.data);

  return (
    <div>
      <DashboardHero
        image="/images/hero-dealer.svg"
        alt="Modern vehicle showroom"
        eyebrow="Dealership workspace"
        title="Connect your dealership to trusted insurers."
        text="Discover insurers, manage partnerships and maintain your vehicle inventory."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={Handshake} label="Insurance partners" value={partnerRows.filter((p) => p.status === "active").length} tone="brand" />
        <Stat icon={Car} label="Vehicles in inventory" value={inventoryRows.length} tone="blue" />
        <Stat icon={Network} label="Pending requests" value={requestRows.filter((r) => r.status === "pending").length} tone="amber" />
      </div>

      {error && <div className="mb-4"><Alert>{error}</Alert></div>}

      <div className="mb-4 flex justify-end">
        <Link to="/dealer/quotes"><Button size="sm" variant="secondary" icon={FileSearch}>Quotation requests</Button></Link>
      </div>

      <Tabs active={tab} onChange={setTab} tabs={[
        { value: "network", label: "Discover insurers" },
        { value: "partnerships", label: "My partnerships" },
        { value: "requests", label: "Requests" },
        { value: "inventory", label: "Inventory" },
      ]} />

      <div className="mt-6">
        {tab === "network" && (
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {insurerRows.map((insurer) => <PartnerCard key={insurer.organization_id} insurer={insurer} onRequest={setRequestInsurer} />)}
            {!insurerRows.length && <p className="text-sm text-ink-500">No verified insurers found.</p>}
          </div>
        )}

        {tab === "partnerships" && (
          <div className="surface divide-y divide-ink-100">
            {partnerRows.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-xs font-bold text-ink-900">{p.insurer_name}</p>
                  <p className="mt-0.5 text-[11px] text-ink-400">Effective {p.effective_date || "—"}</p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={p.status} />
                  {p.status === "active" && <Button size="sm" variant="danger-soft" onClick={() => suspendPartnership.mutate({ id: p.id, reason: "Suspended by the dealership." })}>Suspend</Button>}
                </div>
              </div>
            ))}
            {!partnerRows.length && <p className="p-6 text-sm text-ink-500">No partnerships yet. Discover insurers to get started.</p>}
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

        {tab === "inventory" && (
          <div>
            <div className="mb-4 flex justify-end"><Button size="sm" variant="brand" onClick={() => setTab("add-vehicle")}>Add vehicle</Button></div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {inventoryRows.map((v) => (
                <div key={v.id} className="surface overflow-hidden">
                  {v.photos?.length ? <img src={v.photos[0].image} alt={v.make} className="h-36 w-full object-cover" /> : <div className="grid h-36 place-items-center bg-ink-100 text-ink-300"><Car className="h-8 w-8" /></div>}
                  <div className="p-4">
                    <p className="text-xs font-bold text-ink-900">{v.make} {v.model} ({v.year})</p>
                    <p className="mt-1 text-sm font-bold text-brand-700">{formatCurrency(v.asking_price)}</p>
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <StatusBadge status={v.status} />
                      <div className="flex flex-wrap items-center gap-2">
                        {v.status === "available" && <Button size="sm" variant="brand" icon={FileText} onClick={() => openQuoteModal(v)}>Quote</Button>}
                        <Button size="sm" variant="secondary" icon={ImagePlus} onClick={() => openPhotoModal(v.id)}>
                          Photos{v.photos?.length ? ` (${v.photos.length})` : ""}
                        </Button>
                        {v.status === "available" && <Button size="sm" variant="secondary" onClick={() => markSold.mutate(v.id)}>Mark sold</Button>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {!inventoryRows.length && <p className="text-sm text-ink-500">No vehicles in inventory.</p>}
            </div>
          </div>
        )}

        {tab === "add-vehicle" && (
          <div className="surface p-6">
            <h3 className="font-display text-base font-bold text-ink-950">Add a vehicle</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Input label="Make" value={vehicleForm.make} onChange={(e) => setVehicleForm((c) => ({ ...c, make: e.target.value }))} />
              <Input label="Model" value={vehicleForm.model} onChange={(e) => setVehicleForm((c) => ({ ...c, model: e.target.value }))} />
              <Input label="Year" type="number" value={vehicleForm.year} onChange={(e) => setVehicleForm((c) => ({ ...c, year: e.target.value }))} />
              <Input label="Asking price (KES)" type="number" value={vehicleForm.asking_price} onChange={(e) => setVehicleForm((c) => ({ ...c, asking_price: e.target.value }))} />
              <Select label="Condition" value={vehicleForm.condition} onChange={(e) => setVehicleForm((c) => ({ ...c, condition: e.target.value }))} options={[{ value: "new", label: "New" }, { value: "used", label: "Used" }]} />
              <Select label="Transmission" value={vehicleForm.transmission} onChange={(e) => setVehicleForm((c) => ({ ...c, transmission: e.target.value }))} options={[{ value: "automatic", label: "Automatic" }, { value: "manual", label: "Manual" }]} />
              <Select label="Fuel" value={vehicleForm.fuel_type} onChange={(e) => setVehicleForm((c) => ({ ...c, fuel_type: e.target.value }))} options={["petrol", "diesel", "hybrid", "electric"].map((v) => ({ value: v, label: titleize(v) }))} />
              <Select label="Category" value={vehicleForm.category} onChange={(e) => setVehicleForm((c) => ({ ...c, category: e.target.value }))} options={["saloon", "suv", "pickup", "van", "truck", "bus", "motorcycle"].map((v) => ({ value: v, label: titleize(v) }))} />
            </div>
            <Textarea label="Description" className="mt-4" value={vehicleForm.description} onChange={(e) => setVehicleForm((c) => ({ ...c, description: e.target.value }))} />
            <div className="mt-4 flex gap-2">
              <Button variant="secondary" onClick={() => setTab("inventory")}>Cancel</Button>
              <Button onClick={() => addVehicle.mutate()} loading={addVehicle.isPending}>Save vehicle</Button>
            </div>
          </div>
        )}
      </div>

      <Modal open={Boolean(requestInsurer)} onClose={() => setRequestInsurer(null)} title={`Partner with ${requestInsurer?.display_name}`} footer={<><Button variant="secondary" onClick={() => setRequestInsurer(null)}>Cancel</Button><Button onClick={() => sendRequest.mutate()} loading={sendRequest.isPending}>Send request</Button></>}>
        <div className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Textarea label="Message" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Introduce your dealership and the partnership you have in mind." />
        </div>
      </Modal>

      <Modal
        open={Boolean(photoVehicle)}
        onClose={closePhotoModal}
        title={photoVehicle ? `Photos — ${photoVehicle.make} ${photoVehicle.model}` : "Vehicle photos"}
        footer={<><Button variant="secondary" onClick={closePhotoModal}>Close</Button><Button onClick={() => uploadPhoto.mutate({ vehicleId: photoVehicle.id, file: photoFile, isPrimary: photoPrimary })} loading={uploadPhoto.isPending} disabled={!photoFile}>Upload photo</Button></>}
      >
        <div className="space-y-4">
          {photoError && <Alert>{photoError}</Alert>}
          {photoVehicle?.photos?.length ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {photoVehicle.photos.map((photo) => (
                <div key={photo.id} className="relative overflow-hidden rounded-xl border border-ink-100">
                  <img src={photo.image} alt={`${photoVehicle.make} ${photoVehicle.model}`} className="h-24 w-full object-cover" />
                  {photo.is_primary && (
                    <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-brand-600 px-2 py-0.5 text-[10px] font-bold text-white"><Star className="h-3 w-3" /> Primary</span>
                  )}
                  <button
                    type="button"
                    onClick={() => deletePhoto.mutate({ vehicleId: photoVehicle.id, photoId: photo.id })}
                    className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full bg-ink-950/70 text-white transition hover:bg-red-600"
                    aria-label="Remove photo"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-500">No photos yet. Add the first photo of this vehicle.</p>
          )}

          <div className="rounded-xl border border-dashed border-ink-200 p-4">
            <Input
              key={photoVehicle?.photos?.length || 0}
              label="Add a photo"
              type="file"
              accept="image/*"
              onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
              hint="JPEG or PNG image."
            />
            <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
              <input type="checkbox" checked={photoPrimary} onChange={(e) => setPhotoPrimary(e.target.checked)} className="h-4 w-4 rounded border-ink-300 text-brand-600" />
              Set as primary photo
            </label>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(quoteVehicle)}
        onClose={closeQuoteModal}
        title={quoteVehicle ? `Request quotation — ${quoteVehicle.make} ${quoteVehicle.model}` : "Request quotation"}
        footer={<><Button variant="secondary" onClick={closeQuoteModal}>Cancel</Button><Button onClick={() => requestQuote.mutate()} loading={requestQuote.isPending} disabled={!quoteForm.insurer || !quoteForm.customer || !quoteForm.sum_insured || !quoteForm.desired_start_date}>Submit request</Button></>}
      >
        <div className="space-y-4">
          {quoteError && <Alert>{quoteError}</Alert>}
          {!activePartners.length && <Alert tone="warning">You need an active insurer partnership before you can request a quotation.</Alert>}

          <Select
            label="Insurer"
            value={quoteForm.insurer}
            onChange={(e) => setQuoteForm((c) => ({ ...c, insurer: e.target.value }))}
            placeholder="Select an active partner"
            options={activePartners.map((p) => ({ value: p.insurer_id, label: p.insurer_name }))}
          />

          <div>
            <p className="label">Customer</p>
            {selectedCustomer ? (
              <div className="flex items-center justify-between gap-3 rounded-xl border border-ink-200 bg-ink-50/60 px-3 py-2">
                <div>
                  <p className="text-sm font-semibold text-ink-900">{selectedCustomer.name}</p>
                  <p className="text-xs text-ink-500">{selectedCustomer.email}{selectedCustomer.phone ? ` · ${selectedCustomer.phone}` : ""}</p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => { setSelectedCustomer(null); setQuoteForm((c) => ({ ...c, customer: "" })); }}>Change</Button>
              </div>
            ) : (
              <>
                <SearchInput value={customerQuery} onChange={(e) => setCustomerQuery(e.target.value)} placeholder="Search customer by name, email or phone" />
                {customerQuery.trim().length >= 2 && (
                  <div className="mt-2 max-h-48 overflow-y-auto rounded-xl border border-ink-100">
                    {customerMatches.isLoading ? (
                      <p className="p-3 text-xs text-ink-500">Searching…</p>
                    ) : customerMatches.isError ? (
                      <p className="p-3 text-xs text-ink-500">Customer search failed. Adjust the search to retry.</p>
                    ) : customerResults.length ? (
                      customerResults.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => { setSelectedCustomer(c); setQuoteForm((current) => ({ ...current, customer: c.id })); setCustomerQuery(""); }}
                          className="flex w-full items-center justify-between gap-3 border-b border-ink-50 px-3 py-2 text-left last:border-0 hover:bg-brand-50"
                        >
                          <span className="text-sm font-semibold text-ink-900">{c.name}</span>
                          <span className="text-xs text-ink-500">{c.email}</span>
                        </button>
                      ))
                    ) : (
                      <p className="p-3 text-xs text-ink-500">No matching customers.</p>
                    )}
                  </div>
                )}
                <p className="mt-1.5 text-xs text-ink-400">The customer must already have an AutoInsure Connect account.</p>
              </>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Coverage" value={quoteForm.coverage_type} onChange={(e) => setQuoteForm((c) => ({ ...c, coverage_type: e.target.value }))} options={["comprehensive", "third_party", "third_party_fire_theft", "commercial", "motorcycle"].map((v) => ({ value: v, label: titleize(v) }))} />
            <Input label="Sum insured (KES)" type="number" value={quoteForm.sum_insured} onChange={(e) => setQuoteForm((c) => ({ ...c, sum_insured: e.target.value }))} />
            <Input label="Desired start date" type="date" value={quoteForm.desired_start_date} onChange={(e) => setQuoteForm((c) => ({ ...c, desired_start_date: e.target.value }))} />
          </div>

          <Textarea label="Notes" value={quoteForm.notes} onChange={(e) => setQuoteForm((c) => ({ ...c, notes: e.target.value }))} placeholder="Optional details for the insurer." />
        </div>
      </Modal>
    </div>
  );
}
