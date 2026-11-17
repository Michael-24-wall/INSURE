import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../context/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function renderProtectedRoutes({ roles, initialPath = "/app", homePath = "/app" }) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app" element={<ProtectedRoute roles={roles} />}>
          <Route index element={<div>Protected content</div>} />
        </Route>
        <Route path="/login" element={<div>Login page</div>} />
        <Route path={homePath} element={<div>Protected fallback</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a loader while authentication is loading", () => {
    useAuth.mockReturnValue({ isAuthenticated: false, loading: true, user: null, homePath: "/app" });

    render(
      <MemoryRouter>
        <ProtectedRoute />
      </MemoryRouter>
    );

    expect(screen.getByText("Loading workspace…")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", () => {
    useAuth.mockReturnValue({ isAuthenticated: false, loading: false, user: null, homePath: "/app" });

    renderProtectedRoutes({ user: null });

    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("renders protected content for an authorized user", () => {
    useAuth.mockReturnValue({ isAuthenticated: true, loading: false, user: { role: "customer" }, homePath: "/app" });

    renderProtectedRoutes({ user: { role: "customer" }, initialPath: "/app" });

    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("redirects unauthorized users to their home route", () => {
    useAuth.mockReturnValue({ isAuthenticated: true, loading: false, user: { role: "provider_admin" }, homePath: "/provider" });

    renderProtectedRoutes({ user: { role: "provider_admin" }, initialPath: "/app", homePath: "/provider", roles: ["customer"] });

    expect(screen.getByText("Protected fallback")).toBeInTheDocument();
  });
});
