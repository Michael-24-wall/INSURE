import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import api, { getErrorMessage } from "../api/client";
import { FUEL_TYPES, USAGE_TYPES, VEHICLE_CATEGORIES } from "../lib/constants";
import { titleize } from "../lib/format";
import { useToast } from "../context/ToastContext";
import { Alert, Button, Input, Modal, Select } from "./ui";

const blank = {
  registration_number: "",
  make: "",
  model: "",
  manufacturing_year: new Date().getFullYear(),
  chassis_number: "",
  engine_cc: "",
  category: "saloon",
  fuel_type: "petrol",
  usage: "private",
  estimated_value: "",
  color: "",
  seat_capacity: "",
  is_active: true,
};

export default function VehicleFormModal({ open, onClose, vehicle, onSaved }) {
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    if (!open) return;
    setError("");
    setForm(vehicle ? {
      ...blank,
      ...vehicle,
      manufacturing_year: vehicle.manufacturing_year ?? new Date().getFullYear(),
      estimated_value: vehicle.estimated_value ?? "",
      engine_cc: vehicle.engine_cc ?? "",
      seat_capacity: vehicle.seat_capacity ?? "",
    } : blank);
  }, [open, vehicle]);

  const save = useMutation({
    mutationFn: async (payload) => vehicle ? api.patch(`/vehicles/${vehicle.id}/`, payload) : api.post("/vehicles/", payload),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
      queryClient.invalidateQueries({ queryKey: ["vehicle", data.id] });
      toast.push(vehicle ? "Vehicle updated." : "Vehicle added.", "success");
      onSaved?.(data);
      onClose();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function submit(event) {
    event.preventDefault();
    setError("");
    const payload = {
      ...form,
      manufacturing_year: Number(form.manufacturing_year),
      estimated_value: Number(form.estimated_value || 0),
      engine_cc: form.engine_cc === "" ? null : Number(form.engine_cc),
      seat_capacity: form.seat_capacity === "" ? null : Number(form.seat_capacity),
    };
    save.mutate(payload);
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={vehicle ? "Edit vehicle" : "Add a vehicle"}
      description="Accurate details produce more relevant quotations."
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} loading={save.isPending}>{vehicle ? "Save changes" : "Add vehicle"}</Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Registration number" required value={form.registration_number} onChange={(e) => update("registration_number", e.target.value)} placeholder="KDA 001A" />
          <Input label="Estimated value (KES)" type="number" min="0" required value={form.estimated_value} onChange={(e) => update("estimated_value", e.target.value)} placeholder="1500000" />
          <Input label="Make" required value={form.make} onChange={(e) => update("make", e.target.value)} placeholder="Toyota" />
          <Input label="Model" required value={form.model} onChange={(e) => update("model", e.target.value)} placeholder="Prado" />
          <Input label="Manufacturing year" type="number" min="1950" max={new Date().getFullYear() + 1} required value={form.manufacturing_year} onChange={(e) => update("manufacturing_year", e.target.value)} />
          <Select label="Category" required value={form.category} onChange={(e) => update("category", e.target.value)} options={VEHICLE_CATEGORIES.map((value) => ({ value, label: titleize(value) }))} />
          <Select label="Fuel" value={form.fuel_type} onChange={(e) => update("fuel_type", e.target.value)} options={FUEL_TYPES.map((value) => ({ value, label: titleize(value) }))} />
          <Select label="Usage" value={form.usage} onChange={(e) => update("usage", e.target.value)} options={USAGE_TYPES.map((value) => ({ value, label: titleize(value) }))} />
          <Input label="Engine size (cc)" type="number" min="0" value={form.engine_cc} onChange={(e) => update("engine_cc", e.target.value)} />
          <Input label="Seat capacity" type="number" min="1" value={form.seat_capacity} onChange={(e) => update("seat_capacity", e.target.value)} />
          <Input label="Colour" value={form.color} onChange={(e) => update("color", e.target.value)} />
          <Input label="Chassis number" value={form.chassis_number} onChange={(e) => update("chassis_number", e.target.value)} />
        </div>
      </form>
    </Modal>
  );
}
