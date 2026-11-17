import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  default: { get: vi.fn() },
  listData: (payload) => payload?.results ?? [],
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext";
import CustomerDashboard from "./CustomerDashboard";

describe("CustomerDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { first_name: "Jane" } });
  });

  it("renders the loading state", () => {
    vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
      const key = queryKey[0];
      if (key === "dashboard") return { isLoading: true };
      return { isLoading: false };
    });

    render(
      <MemoryRouter>
        <CustomerDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText("Loading workspace…")).toBeInTheDocument();
  });

  it("renders the customer policy empty state", () => {
    vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
      const key = queryKey[0];
      if (key === "dashboard") return { isLoading: false, data: { data: { active_policies: 0, policies_expiring_soon: 0, vehicles: 0, open_claims: 0, total_paid: "0" } } };
      if (key === "policies" || key === "claims" || key === "applications") return { isLoading: false, data: [] };
      return { isLoading: false, data: [] };
    });

    render(
      <MemoryRouter>
        <CustomerDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText("No policy yet")).toBeInTheDocument();
    expect(screen.getByText("Start a quotation")).toBeInTheDocument();
  });
});
