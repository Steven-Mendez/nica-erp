import { describe, expect, it } from "vitest";

import { normalizeRuc, RUC_PLACEHOLDER } from "@/features/tenants/lib/ruc";

describe("normalizeRuc", () => {
  it("uppercases letters", () => {
    expect(normalizeRuc("j03100000")).toBe("J03100000");
  });

  it("strips dashes and other punctuation", () => {
    expect(normalizeRuc("J03-100000-00010")).toBe("J0310000000010");
  });

  it("is idempotent", () => {
    const once = normalizeRuc("J03-100000-00010-X");
    expect(normalizeRuc(once)).toBe(once);
  });

  it("round-trips the documented placeholder", () => {
    expect(normalizeRuc(RUC_PLACEHOLDER)).toBe("J0310000000010");
  });
});
