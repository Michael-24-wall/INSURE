import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("axios", () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  };
  const axios = { create: vi.fn(() => instance), get: vi.fn(), post: vi.fn() };
  return { default: axios, ...axios };
});

import axios from "axios";
import { getErrorMessage, listData, pageCount } from "../api/client";

describe("api client helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("extracts list data from arrays and paginated responses", () => {
    expect(listData([{ id: "1" }])).toEqual([{ id: "1" }]);
    expect(listData({ results: [{ id: "2" }] })).toEqual([{ id: "2" }]);
    expect(listData({})).toEqual([]);
  });

  it("calculates page counts", () => {
    expect(pageCount([{ id: "1" }])).toBe(1);
    expect(pageCount({ count: 41, results: Array.from({ length: 25 }, (_, i) => ({ id: String(i) })) })).toBe(41);
  });

  it("prefers API error detail messages", () => {
    expect(getErrorMessage({ response: { data: { detail: "Not permitted" } } })).toBe("Not permitted");
    expect(getErrorMessage({ response: { data: "Bad request" } })).toBe("Bad request");
    expect(getErrorMessage({ response: { data: { error: { message: "Payment failed" } } } })).toBe("Payment failed");
  });

  it("falls back to a generic request error", () => {
    expect(getErrorMessage({ message: "Network down" })).toBe("Network down");
    expect(getErrorMessage({})).toBe("Something went wrong. Please try again.");
  });

  it("creates an axios instance with an API base URL and timeout", () => {
    expect(axios.create).toHaveBeenCalledWith(expect.objectContaining({ baseURL: "/api/v1", timeout: 45000 }));
  });
});
