import { describe, expect, it } from "vitest";

import { compactCurrency, formatCurrency, formatDate, formatDateTime, localDateTimeISO, titleize, todayISO } from "./format";

describe("format helpers", () => {
  it("formats currency values", () => {
    expect(formatCurrency("12500")).toContain("12,500");
    expect(formatCurrency(0)).toContain("0");
    expect(formatCurrency(null)).toContain("0");
    expect(formatCurrency("invalid")).toContain("0");
    expect(compactCurrency(12500)).toContain("12.5");
  });

  it("formats dates and datetimes", () => {
    expect(formatDate("2026-11-12T10:30:00Z")).toBe("12 Nov 2026");
    expect(formatDateTime("2026-11-12T10:30:00Z")).toBe("12 Nov 2026, 10:30");
  });

  it("normalizes titles and generates local date values", () => {
    expect(titleize("customer_status")).toBe("Customer Status");
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(localDateTimeISO()).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });
});
