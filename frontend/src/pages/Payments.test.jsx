import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("../api/client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: () => "Request failed.",
  listData: (payload) => payload?.results ?? [],
  pageCount: (payload) => payload?.count ?? 0,
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../context/ToastContext", () => ({
  useToast: vi.fn(() => ({ push: vi.fn() })),
}));

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import Payments from "./Payments";

const payment = {
  id: 1,
  reference: "PAY-TEST-1",
  created_at: "2026-11-12T10:00:00Z",
  purpose: "premium",
  application_number: "APP-1",
  user_name: "Jane Customer",
  amount: "2500.00",
  method: "bank",
  status: "pending",
  can_verify: true,
};

function mockQueries({ rows = [payment], counts = {}, error = false } = {}) {
  vi.mocked(useQuery).mockImplementation(({ queryKey }) => {
    if (queryKey[1] === "counts") {
      return { isLoading: false, isError: false, data: counts };
    }
    return {
      isLoading: false,
      isError: error,
      data: { results: rows, count: rows.length },
      refetch: vi.fn(),
    };
  });
}

function renderPayments(path = "/app/payments") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Payments />
    </MemoryRouter>
  );
}

describe("Payments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { id: 1, role: "customer" } });
  });

  it("renders an empty state for customers without payments", () => {
    mockQueries({ rows: [], counts: { pending: 0, processing: 0, succeeded: 0, failed: 0, refunded: 0 } });

    renderPayments();

    expect(screen.getByText("No payments yet")).toBeInTheDocument();
  });

  it("renders a list error with a retry action", () => {
    mockQueries({ error: true });

    renderPayments();

    expect(screen.getByText(/Could not load this list/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("requires a provider reference before confirming a manual payment", () => {
    useAuth.mockReturnValue({ user: { id: 2, role: "provider_admin" } });
    mockQueries({ counts: { pending: 1, processing: 0, succeeded: 0, failed: 0, refunded: 0 } });

    renderPayments("/provider/payments");
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));

    const confirm = screen.getByRole("button", { name: "Confirm payment" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Provider \/ transaction reference/), {
      target: { value: "BANK-REF-123" },
    });

    expect(confirm).toBeEnabled();
  });
});
