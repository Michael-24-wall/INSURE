import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("../../api/client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: () => "Request failed.",
  listData: (payload) => payload?.results ?? [],
}));

vi.mock("../../context/ToastContext", () => ({
  useToast: vi.fn(() => ({ push: vi.fn() })),
}));

import { useQuery } from "@tanstack/react-query";
import VehicleDetail from "./VehicleDetail";

const vehicle = {
  id: 7,
  registration_number: "KCA 123A",
  make: "Toyota",
  model: "RAV4",
  manufacturing_year: 2020,
  category: "suv",
  fuel_type: "petrol",
  usage: "private",
  color: "White",
  estimated_value: "3500000.00",
  chassis_number: "",
  engine_cc: 2000,
  seat_capacity: 5,
  created_at: "2026-01-10T09:00:00Z",
  is_active: true,
};

function mockQueries({ documentsError = false, inspectionsError = false } = {}) {
  vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
    const key = queryKey[0];
    if (key === "vehicle") {
      return { isLoading: false, isError: false, data: vehicle };
    }
    if (key === "vehicle-documents") {
      return { isLoading: false, isError: documentsError, data: [], refetch: vi.fn() };
    }
    if (key === "inspections") {
      return { isLoading: false, isError: inspectionsError, data: { results: [], count: 0 }, refetch: vi.fn() };
    }
    return { isLoading: false, isError: false, data: [] };
  });
}

function renderVehicle() {
  return render(
    <MemoryRouter initialEntries={["/app/vehicles/7"]}>
      <Routes>
        <Route path="/app/vehicles/:id" element={<VehicleDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("VehicleDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not present a failed document request as an empty document list", () => {
    mockQueries({ documentsError: true });

    renderVehicle();

    expect(screen.getByText(/Could not load documents/)).toBeInTheDocument();
    expect(screen.queryByText("No documents uploaded.")).not.toBeInTheDocument();
  });

  it("does not present a failed inspection request as no inspections", () => {
    mockQueries({ inspectionsError: true });

    renderVehicle();

    expect(screen.getByText(/Could not load inspections/)).toBeInTheDocument();
    expect(screen.queryByText("No inspections for this vehicle.")).not.toBeInTheDocument();
  });
});
