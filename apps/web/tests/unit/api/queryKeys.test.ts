import { describe, expect, it } from "vitest";
import { meQueryKey } from "@/api/queryKeys";

describe("meQueryKey", () => {
  it("is the canonical ['auth', 'me'] tuple", () => {
    expect(meQueryKey).toEqual(["auth", "me"]);
  });

  it("is a stable reference (modules import the same array)", async () => {
    const { meQueryKey: again } = await import("@/api/queryKeys");
    expect(again).toBe(meQueryKey);
  });
});
