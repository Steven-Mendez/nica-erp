// Unit tests for nextRouteForCurrentState — covers all branches:
// no profile, no memberships, picker-not-confirmed, missing active
// tenant, exempt routes.
import { afterEach, describe, expect, it, vi } from "vitest";
import { PICKER_FLAG_KEY, nextRouteForCurrentState, setPickerConfirmed } from "@/lib/route-guard";

vi.mock("@/features/auth/api/endpoints", () => ({
  getMe: vi.fn(),
}));
vi.mock("@/features/tenants/api/endpoints", () => ({
  getMyTenants: vi.fn(),
}));

import { getMe } from "@/features/auth/api/endpoints";
import { getMyTenants } from "@/features/tenants/api/endpoints";

const meMock = vi.mocked(getMe);
const tenantsMock = vi.mocked(getMyTenants);

const makeMe = (
  over: Partial<Awaited<ReturnType<typeof getMe>>> = {},
): Awaited<ReturnType<typeof getMe>> => ({
  id: "00000000-0000-0000-0000-000000000001",
  email: "a@b.io",
  display_name: "Ada",
  locale: null,
  timezone: "Europe/Madrid",
  preferences: {},
  active_tenant: "00000000-0000-0000-0000-0000000000aa",
  role: "owner",
  permissions: [],
  ...over,
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("nextRouteForCurrentState", () => {
  it("redirects to /welcome when display_name is null", async () => {
    meMock.mockResolvedValueOnce(makeMe({ display_name: null }));
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    expect(next).toBe("/welcome");
  });

  it("does NOT redirect /account when display_name is null", async () => {
    meMock.mockResolvedValueOnce(makeMe({ display_name: null }));
    tenantsMock.mockResolvedValueOnce({ items: [] });
    const next = await nextRouteForCurrentState({ pathname: "/account" });
    expect(next).toBeNull();
  });

  it("redirects to /onboarding when memberships is empty", async () => {
    meMock.mockResolvedValueOnce(makeMe({ active_tenant: null }));
    tenantsMock.mockResolvedValueOnce({ items: [] });
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    expect(next).toBe("/onboarding");
  });

  it("does NOT redirect /onboarding when zero memberships", async () => {
    meMock.mockResolvedValueOnce(makeMe({ active_tenant: null }));
    tenantsMock.mockResolvedValueOnce({ items: [] });
    const next = await nextRouteForCurrentState({ pathname: "/onboarding" });
    expect(next).toBeNull();
  });

  it("redirects to /tenants when memberships exist but no active tenant", async () => {
    meMock.mockResolvedValueOnce(makeMe({ active_tenant: null }));
    tenantsMock.mockResolvedValueOnce({
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Org",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    expect(next).toBe("/tenants");
  });

  it("returns null when fully provisioned AND the picker is confirmed", async () => {
    setPickerConfirmed();
    meMock.mockResolvedValueOnce(makeMe());
    tenantsMock.mockResolvedValueOnce({
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Org",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    expect(next).toBeNull();
  });

  it("forces /tenants when memberships exist but the picker has not been confirmed", async () => {
    meMock.mockResolvedValueOnce(makeMe());
    tenantsMock.mockResolvedValueOnce({
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Org",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    // No setPickerConfirmed() — beforeEach in tests/setup.ts already
    // cleared sessionStorage.
    expect(window.sessionStorage.getItem(PICKER_FLAG_KEY)).toBeNull();
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    expect(next).toBe("/tenants");
  });

  it("does NOT force /tenants for routes in TENANT_EXEMPT (e.g. /account)", async () => {
    meMock.mockResolvedValueOnce(makeMe());
    tenantsMock.mockResolvedValueOnce({
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Org",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    const next = await nextRouteForCurrentState({ pathname: "/account" });
    expect(next).toBeNull();
  });

  it("does NOT loop redirect /tenants itself when the picker is unconfirmed", async () => {
    meMock.mockResolvedValueOnce(makeMe());
    tenantsMock.mockResolvedValueOnce({
      items: [
        {
          tenant_id: "00000000-0000-0000-0000-0000000000aa",
          name: "Org",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    const next = await nextRouteForCurrentState({ pathname: "/tenants" });
    expect(next).toBeNull();
  });
});
