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

import { useQuery } from "@tanstack/react-query";
import ProviderDashboard from "./ProviderDashboard";

describe("ProviderDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the financial operations loading state", () => {
    vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
      const key = queryKey[0];
      if (key === "dashboard" || key === "finance") return { isLoading: true };
      return { isLoading: false };
    });

    render(
      <MemoryRouter>
        <ProviderDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText("Loading workspace…")).toBeInTheDocument();
  });

  it("renders financial operations metrics from the finance dashboard", () => {
    vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
      const key = queryKey[0];
      if (key === "dashboard") {
        return { isLoading: false, data: { data: { active_products: 1, products: 2, applications_pending: 0, applications_received: 0, active_policies: 1, policies_expiring_soon: 0, premium_collected: "1000", payments_awaiting_verification: 0, claims_requiring_action: 0, inspections_scheduled: 0, open_quotation_requests: 0 } } };
      }
      if (key === "finance") {
        return { isLoading: false, data: { net_premium_collected: "1000", premium_earned_recognized: "1000", commissions_outstanding: "10", outstanding_settlements: "5" } };
      }
      return { isLoading: false, data: [] };
    });

    render(
      <MemoryRouter>
        <ProviderDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText("Net premium collected")).toBeInTheDocument();
    expect(screen.getAllByText("KES 1,000")).toHaveLength(3);
    expect(screen.getByText("Premium earned")).toBeInTheDocument();
    expect(screen.getByText("KES 10")).toBeInTheDocument();
    expect(screen.getByText("Commissions outstanding")).toBeInTheDocument();
    expect(screen.getByText("Outstanding settlements")).toBeInTheDocument();
    expect(screen.getByText("KES 5")).toBeInTheDocument();
  });

  it("surfaces a financial dashboard error state", () => {
    vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
      const key = queryKey[0];
      if (key === "dashboard") return { isLoading: false, data: { data: {} }, isError: false };
      if (key === "finance") return { isLoading: false, data: undefined, isError: true };
      return { isLoading: false, data: [] };
    });

    render(
      <MemoryRouter>
        <ProviderDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText("We couldn't load this dashboard.")).toBeInTheDocument();
  });
});
