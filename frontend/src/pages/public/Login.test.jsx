import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../context/AuthContext", () => ({
  useAuth: vi.fn(() => ({ login: vi.fn(), verifyTwoFactor: vi.fn() })),
}));

import Login from "./Login";

describe("Login", () => {
  it("shows the password-reset success notice returned by navigation state", () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: "/login", state: { notice: "Password reset. Please sign in." } }]}>
        <Login />
      </MemoryRouter>
    );

    expect(screen.getByText("Password reset. Please sign in.")).toBeInTheDocument();
  });
});
