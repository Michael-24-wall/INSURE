import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Car, FileSearch, MoreHorizontal, Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import api, { listData, getErrorMessage } from "../../api/client";
import { formatCurrency, titleize } from "../../lib/format";
import VehicleFormModal from "../../components/VehicleFormModal";
import { useToast } from "../../context/ToastContext";
import { Alert, Button, EmptyState, PageHeader, PageLoader, SearchInput, Stat } from "../../components/ui";
import { StatusBadge } from "../../components/ui";

export default function Vehicles() {
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editVehicle, setEditVehicle] = useState(null);
  const [menuId, setMenuId] = useState(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  const query = useQuery({
    queryKey: ["vehicles", search],
    queryFn: async () => (await api.get(`/vehicles/?page_size=100&search=${encodeURIComponent(search)}`)).data,
  });

  const remove = async (vehicle) => {
    if (!window.confirm(`Remove ${vehicle.registration_number}? This soft-deletes the vehicle.`)) return;
    try {
      await api.delete(`/vehicles/${vehicle.id}/`);
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
      toast.push("Vehicle removed.", "success");
    } catch (err) {
      toast.push(getErrorMessage(err), "error");
    }
    setMenuId(null);
  };

  const rows = listData(query.data);
  const totalValue = rows.reduce((sum, vehicle) => sum + Number(vehicle.estimated_value || 0), 0);

  return (
    <div>
      <PageHeader
        eyebrow="Garage"
        title="Your vehicles"
        description="Keep vehicle details current for accurate quotations, inspections and claims."
        actions={<Button icon={Plus} onClick={() => { setEditVehicle(null); setModalOpen(true); }}>Add vehicle</Button>}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat icon={Car} label="Vehicles" value={rows.length} hint="Active records" />
        <Stat icon={ShieldCheck} label="Total estimated value" value={formatCurrency(totalValue)} tone="ink" />
        <Stat icon={FileSearch} label="Ready for quotes" value={rows.filter((v) => v.is_active).length} tone="lime" />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SearchInput value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search registration, make or model" className="w-full sm:w-80" />
        <p className="text-xs text-ink-400">{rows.length} vehicle{rows.length === 1 ? "" : "s"}</p>
      </div>

      {query.isLoading ? <PageLoader /> : query.isError ? (
        <div className="surface p-5"><Alert title="We couldn't load your vehicles">Please check your connection and try again.</Alert></div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((vehicle) => (
            <div key={vehicle.id} className="surface group overflow-hidden">
              <div className="relative h-32 overflow-hidden bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-5">
                <div className="landing-grid absolute inset-0 opacity-30" />
                <div className="relative flex items-start justify-between">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">{titleize(vehicle.category)}</p>
                    <p className="mt-1 font-display text-xl font-bold text-white">{vehicle.registration_number}</p>
                    <p className="text-xs text-white/50">{vehicle.make} {vehicle.model} · {vehicle.manufacturing_year}</p>
                  </div>
                  <Car className="h-10 w-10 text-lime-300/70" />
                </div>
              </div>
              <div className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">Estimated value</p>
                    <p className="text-sm font-bold text-ink-950">{formatCurrency(vehicle.estimated_value)}</p>
                  </div>
                  <StatusBadge status={vehicle.is_active ? "active" : "cancelled"} label={vehicle.is_active ? "Active" : "Inactive"} />
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-ink-100 pt-3">
                  <div className="flex gap-3 text-[11px] text-ink-400">
                    <span>{titleize(vehicle.fuel_type)}</span>
                    <span>·</span>
                    <span>{titleize(vehicle.usage)}</span>
                  </div>
                  <div className="relative flex items-center gap-1">
                    <Link to={`/app/vehicles/${vehicle.id}`} className="rounded-lg px-2 py-1.5 text-[11px] font-bold text-brand-700 hover:bg-brand-50">Open</Link>
                    <button onClick={() => setMenuId(menuId === vehicle.id ? null : vehicle.id)} className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100" aria-label="Vehicle actions">
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                    {menuId === vehicle.id && (
                      <>
                        <div className="fixed inset-0 z-20" onClick={() => setMenuId(null)} />
                        <div className="absolute bottom-8 right-0 z-30 w-36 rounded-xl border border-ink-100 bg-white p-1 shadow-soft">
                          <button onClick={() => { setEditVehicle(vehicle); setModalOpen(true); setMenuId(null); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-ink-600 hover:bg-ink-50"><Pencil className="h-3.5 w-3.5" /> Edit</button>
                          <button onClick={() => remove(vehicle)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-red-600 hover:bg-red-50"><Trash2 className="h-3.5 w-3.5" /> Remove</button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <button onClick={() => { setEditVehicle(null); setModalOpen(true); }} className="flex min-h-[250px] flex-col items-center justify-center rounded-3xl border border-dashed border-ink-200 bg-white/50 p-6 text-center transition hover:border-brand-300 hover:bg-brand-50/30">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-ink-950 text-lime-300"><Plus className="h-5 w-5" /></span>
            <p className="mt-4 text-sm font-bold text-ink-900">Add another vehicle</p>
            <p className="mt-1 max-w-[220px] text-xs text-ink-400">More vehicles mean more cover options and a complete garage view.</p>
          </button>
        </div>
      )}
      {!query.isLoading && !query.isError && !rows.length && (
        <EmptyState
          icon={Car}
          title="Your garage is empty"
          description="Add your first vehicle to request comparable quotations from verified insurers."
          action={<Button icon={Plus} onClick={() => setModalOpen(true)}>Add your first vehicle</Button>}
        />
      )}

      <VehicleFormModal open={modalOpen} onClose={() => setModalOpen(false)} vehicle={editVehicle} />
    </div>
  );
}
