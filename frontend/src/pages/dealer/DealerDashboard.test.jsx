import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("../../api/client", () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
  getErrorMessage: () => "Request failed.",
  listData: (payload) => payload?.results ?? [],
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../../context/ToastContext", () => ({
  useToast: vi.fn(() => ({ push: vi.fn() })),
}));

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext";
import DealerDashboard from "./DealerDashboard";

function mockQueries({ errorKey } = {}) {
  vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
    const key = queryKey[0];
    return {
      isLoading: false,
      isError: key === errorKey,
      data: [],
      refetch: vi.fn(),
    };
  });
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DealerDashboard />
    </MemoryRouter>
  );
}

describe("DealerDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      user: {
        id: 4,
        role: "dealer_admin",
        memberships: [{ organization_type: "dealer", organization_id: 9 }],
      },
    });
  });

  it("renders a loading state while the dealership workspace loads", () => {
    vi.mocked(useQuery).mockReturnValue({ isLoading: true, isError: false, data: undefined });

    renderDashboard();

    expect(screen.getByText("Loading workspace…")).toBeInTheDocument();
  });

  it("surfaces a workspace error instead of empty lists", () => {
    mockQueries({ errorKey: "inventory" });

    renderDashboard();

    expect(screen.getByText("We couldn't load your dealership workspace.")).toBeInTheDocument();
  });

  it("shows the network empty state when there are no verified insurers", () => {
    mockQueries();

    renderDashboard();

    expect(screen.getByText("No verified insurers found.")).toBeInTheDocument();
    expect(screen.getByText("Vehicles in inventory")).toBeInTheDocument();
  });
});
