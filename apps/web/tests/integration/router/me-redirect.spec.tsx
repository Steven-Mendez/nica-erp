// Integration spec for the `/me` route. Asserts the unconditional
// redirect to `/account` defined in `src/router.ts`. With a stubbed
// access token + me/tenants payloads, the chain lands on `/account`;
// without a token, it resolves to `/login` via `/account`'s guard.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
}));

vi.mock("@/features/auth/api/endpoints", () => ({
  getMe: vi.fn(),
}));

vi.mock("@/features/tenants/api/endpoints", () => ({
  getMyTenants: vi.fn(),
}));

import { getAccessToken } from "@/api/tokenStore";
import { getMe } from "@/features/auth/api/endpoints";
import { getMyTenants } from "@/features/tenants/api/endpoints";
import { setPickerConfirmed } from "@/lib/route-guard";
import { router } from "@/router";

const accessTokenMock = vi.mocked(getAccessToken);
const meMock = vi.mocked(getMe);
const tenantsMock = vi.mocked(getMyTenants);

const TENANT_ID = "00000000-0000-0000-0000-0000000000aa";

beforeEach(() => {
  accessTokenMock.mockReset();
  meMock.mockReset();
  tenantsMock.mockReset();
});

describe("/me route", () => {
  it("redirects to /account when an access token is present", async () => {
    accessTokenMock.mockReturnValue("test-access-token");
    meMock.mockResolvedValue({
      id: "00000000-0000-0000-0000-000000000001",
      email: "ada@nica.test",
      display_name: "Ada Lovelace",
      locale: "es-NI",
      timezone: "America/Managua",
      preferences: {},
      active_tenant: TENANT_ID,
      role: "owner",
      permissions: [],
    });
    tenantsMock.mockResolvedValue({
      items: [
        {
          tenant_id: TENANT_ID,
          name: "Acme S.A.",
          role: "owner",
          status: "active",
          joined_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    setPickerConfirmed();

    await router.navigate({ to: "/me" });
    await router.load();

    expect(router.state.location.pathname).toBe("/account");
  });

  it("redirects to /login when no access token is present", async () => {
    accessTokenMock.mockReturnValue(null);

    await router.navigate({ to: "/me" });
    await router.load();

    expect(router.state.location.pathname).toBe("/login");
  });
});
