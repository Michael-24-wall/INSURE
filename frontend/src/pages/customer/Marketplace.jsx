import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Gauge, HeartPulse, ShieldCheck, Store, Zap } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { formatCurrency } from "../../lib/format";
import { INSURANCE_LINES, PRODUCT_CATEGORIES } from "../../lib/constants";
import { SplashBanner } from "../../components/Hero";
import { Alert, Button, Input, Select, Textarea } from "../../components/ui";

function inDays(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export default function Marketplace() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [vehicleId, setVehicleId] = useState(params.get("vehicle") || "");
  const [line, setLine] = useState(params.get("line") || "motor");
  const [coverageType, setCoverageType] = useState("comprehensive");
  const [sumInsured, setSumInsured] = useState("");
  const [startDate, setStartDate] = useState(inDays(1));
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const vehicles = useQuery({
    queryKey: ["vehicles", "marketplace"],
    queryFn: async () => (await api.get("/vehicles/?page_size=100")).data,
  });
  const products = useQuery({
    queryKey: ["products", "marketplace"],
    queryFn: async () => (await api.get("/products/?page_size=100&is_active=true")).data,
  });

  const vehicleRows = listData(vehicles.data);
  const productRows = listData(products.data);
  const selectedVehicle = vehicleRows.find((vehicle) => String(vehicle.id) === String(vehicleId));
  const selectedLine = INSURANCE_LINES.find((item) => item.value === line) || INSURANCE_LINES[0];
  const isMotor = selectedLine.value === "motor";

  useEffect(() => {
    if (selectedVehicle && !sumInsured) setSumInsured(selectedVehicle.estimated_value);
  }, [selectedVehicle, sumInsured]);

  const createRequest = useMutation({
    mutationFn: async () => (await api.post("/quotation-requests/", {
      vehicle: vehicleId,
      coverage_type: coverageType,
      sum_insured: Number(sumInsured),
      desired_start_date: startDate,
      notes,
    })).data,
    onSuccess: (data) => navigate(`/app/quotes/${data.id}`),
    onError: (err) => setError(getErrorMessage(err)),
  });

  function submit(event) {
    event.preventDefault();
    setError("");
    if (!vehicleId) {
      setError("Choose a vehicle first.");
      return;
    }
    createRequest.mutate();
  }

  const matchingProducts = productRows.filter((product) => product.category === coverageType);
  const insurerCount = new Set(matchingProducts.map((product) => product.insurer)).size;

  return (
    <div>
      <SplashBanner
        image="/images/hero-marketplace.svg"
        alt="Connected insurance marketplace"
        eyebrow="Insurance marketplace"
        title="Find the right protection"
        text="Choose an insurance line to explore products published by verified providers. Live quotation requests currently support motor products."
        className="mb-6 rounded-3xl"
      />

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="surface p-6 sm:p-7">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700"><HeartPulse className="h-5 w-5" /></span>
            <div>
              <h2 className="font-display text-lg font-bold text-ink-950">Choose your insurance needs</h2>
              <p className="text-xs text-ink-400">Product availability is determined by verified providers.</p>
            </div>
          </div>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {INSURANCE_LINES.map((item) => (
              <button
                type="button"
                key={item.value}
                onClick={() => setLine(item.value)}
                className={`rounded-2xl border p-3 text-left transition ${line === item.value ? "border-brand-300 bg-brand-50" : "border-ink-100 bg-white hover:border-brand-200"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-ink-900">{item.label}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${item.status === "live" ? "bg-brand-700 text-white" : "bg-ink-100 text-ink-500"}`}>
                    {item.status === "live" ? "Live" : "Expanding"}
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-ink-500">{item.description}</p>
              </button>
            ))}
          </div>

          {isMotor ? (
            <form onSubmit={submit} className="mt-7 border-t border-ink-100 pt-6">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700"><Store className="h-5 w-5" /></span>
            <div>
              <h2 className="font-display text-lg font-bold text-ink-950">Request motor quotations</h2>
              <p className="text-xs text-ink-400">Live motor products from verified insurers. No obligation to buy.</p>
            </div>
          </div>

          <div className="mt-6 space-y-5">
            {error && <Alert>{error}</Alert>}
            {!vehicleRows.length && !vehicles.isLoading && <Alert tone="warning">Add a vehicle to your garage before requesting a quotation.</Alert>}
            <Select
              label="Vehicle"
              required
              placeholder="Select your vehicle"
              value={vehicleId}
              onChange={(event) => { setVehicleId(event.target.value); setSumInsured(""); }}
              options={vehicleRows.map((vehicle) => ({ value: vehicle.id, label: `${vehicle.registration_number} · ${vehicle.make} ${vehicle.model} (${vehicle.manufacturing_year})` }))}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                label="Cover type"
                required
                value={coverageType}
                onChange={(event) => setCoverageType(event.target.value)}
                options={PRODUCT_CATEGORIES}
              />
              <Input label="Sum insured (KES)" type="number" min="1" required value={sumInsured} onChange={(event) => setSumInsured(event.target.value)} hint={selectedVehicle ? `Vehicle estimate: ${formatCurrency(selectedVehicle.estimated_value)}` : "Usually the vehicle's market value"} />
              <Input label="Cover start date" type="date" required min={inDays(0)} value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              <div className="flex items-end">
                <div className="flex w-full items-center gap-2 rounded-xl border border-ink-100 bg-ink-50/60 px-3.5 py-3 text-xs text-ink-500">
                  <Zap className="h-4 w-4 text-amber-500" /> Quotes typically arrive within minutes
                </div>
              </div>
            </div>
            <Textarea label="Anything else?" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Optional: preferred excess, specific benefits or questions for insurers." />
            <Button type="submit" size="lg" className="w-full" loading={createRequest.isPending} disabled={!vehicleRows.length}>Request quotations <ArrowRight className="h-4 w-4" /></Button>
          </div>
        </form>
          ) : (
            <div className="mt-7 rounded-2xl border border-dashed border-ink-200 bg-ink-50/70 p-6 text-center">
              <ShieldCheck className="mx-auto h-7 w-7 text-brand-600" />
              <h3 className="mt-3 font-display text-base font-bold text-ink-900">{selectedLine.label} products are being onboarded</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-500">
                This line is part of the INSURECONNECT ecosystem architecture, but the current backend does not yet support genuine {selectedLine.label.toLowerCase()} quotations. We will not present placeholder products or simulated purchases.
              </p>
              <Link to="/register?type=provider" className="mt-4 inline-flex"><Button variant="dark" size="sm">Become a provider <ArrowRight className="h-4 w-4" /></Button></Link>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6 text-white">
            <p className="eyebrow !text-lime-300">Live marketplace</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-display text-3xl font-bold">{isMotor ? insurerCount || "—" : "—"}</p>
                <p className="mt-1 text-[11px] text-white/50">{isMotor ? "matching insurers" : "line providers"}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-display text-3xl font-bold">{isMotor ? matchingProducts.length || "—" : "—"}</p>
                <p className="mt-1 text-[11px] text-white/50">{isMotor ? "matching products" : "published products"}</p>
              </div>
            </div>
            <div className="mt-5 space-y-3 text-xs text-white/60">
              <p className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-lime-300" /> Verified providers only</p>
              <p className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-lime-300" /> Side-by-side quote comparison</p>
              <p className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-lime-300" /> Transparent benefits and exclusions</p>
            </div>
          </div>

          <div className="surface p-5">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-brand-600" />
              <p className="text-sm font-bold text-ink-900">About {selectedLine.label}</p>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">
              {!isMotor
                ? `${selectedLine.label} discovery is available as the ecosystem expands. Product availability and underwriting remain provider-led.`
                : coverageType === "comprehensive"
                ? "Comprehensive cover protects your own vehicle plus third-party liability, subject to the policy terms."
                : coverageType === "third_party"
                  ? "Third-party cover protects other people and their property. It is the legal minimum for many vehicles."
                  : "This cover balances protection for your vehicle with third-party liability, subject to the selected product."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
