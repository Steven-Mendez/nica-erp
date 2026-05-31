// apps/web/tests/unit/features/auth/api/endpoints.test.ts
//
// The auth endpoints are thin wrappers around `api.POST` / `api.GET` /
// `api.PATCH`. Integration tests for hooks only ever drive the happy path,
// leaving the ApiError + undefined-data branches uncovered. This file pins
// every endpoint's URL/body wiring and the shared error helpers.

import { beforeEach, describe, expect, it, vi } from "vitest";

const { postMock, getMock, patchMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
  patchMock: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  api: { POST: postMock, GET: getMock, PATCH: patchMock },
}));

import {
  ApiError,
  changePassword,
  confirmSignup,
  forgotPassword,
  getMe,
  login,
  logout,
  patchMe,
  refresh,
  register,
  resendCode,
  resetPassword,
} from "@/features/auth/api/endpoints";

const ok = <T>(data: T, status = 200) => ({
  data,
  response: { status } as Response,
});

const fail = (status: number, errorBody: unknown) => ({
  error: errorBody,
  response: { status } as Response,
});

const undef = (status: number) => ({
  data: undefined,
  response: { status } as Response,
});

describe("ApiError", () => {
  it("carries label, status, and parsed detail", () => {
    const err = new ApiError("POST /v1/auth/login", 401, { code: "x" });
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ApiError");
    expect(err.message).toBe("POST /v1/auth/login failed: 401");
    expect(err.status).toBe(401);
    expect(err.detail).toEqual({ code: "x" });
  });
});

describe("auth endpoints — happy paths and URL/body wiring", () => {
  beforeEach(() => {
    postMock.mockReset();
    getMock.mockReset();
    patchMock.mockReset();
  });

  it("register POSTs /v1/auth/register and returns RegisterResponse", async () => {
    postMock.mockResolvedValueOnce(ok({ user_id: "u-1" }));
    const out = await register({
      email: "a@b.test",
      password: "Passw0rd!Passw0rd",
    });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/register", {
      body: {
        email: "a@b.test",
        password: "Passw0rd!Passw0rd",
      },
    });
    expect(out).toEqual({ user_id: "u-1" });
  });

  it("confirmSignup without password resolves null on 204", async () => {
    postMock.mockResolvedValueOnce(ok(undefined, 204));
    await expect(confirmSignup({ email: "a@b.test", code: "123456" })).resolves.toBeNull();
    expect(postMock).toHaveBeenCalledWith("/v1/auth/confirm-signup", {
      body: { email: "a@b.test", code: "123456" },
    });
  });

  it("confirmSignup with password resolves token bundle on 200", async () => {
    postMock.mockResolvedValueOnce(
      ok({ access_token: "a", refresh_token: "r", id_token: "i", token_type: "Bearer" }),
    );
    await expect(
      confirmSignup({ email: "a@b.test", code: "123456", password: "Passw0rd!Passw0rd" }),
    ).resolves.toEqual({
      access_token: "a",
      refresh_token: "r",
      id_token: "i",
      token_type: "Bearer",
    });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/confirm-signup", {
      body: { email: "a@b.test", code: "123456", password: "Passw0rd!Passw0rd" },
    });
  });

  it("resendCode POSTs /v1/auth/resend-code", async () => {
    postMock.mockResolvedValueOnce(ok({}));
    await resendCode({ email: "a@b.test" });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/resend-code", {
      body: { email: "a@b.test" },
    });
  });

  it("login POSTs /v1/auth/login and returns TokenResponse", async () => {
    const tokens = {
      access_token: "at",
      refresh_token: "rt",
      id_token: "it",
      token_type: "Bearer",
      expires_in: 3600,
    };
    postMock.mockResolvedValueOnce(ok(tokens));
    await expect(login({ email: "a@b.test", password: "x" })).resolves.toEqual(tokens);
    expect(postMock).toHaveBeenCalledWith("/v1/auth/login", {
      body: { email: "a@b.test", password: "x" },
    });
  });

  it("refresh POSTs /v1/auth/refresh and returns TokenResponse", async () => {
    const tokens = {
      access_token: "at2",
      refresh_token: "rt2",
      id_token: "it2",
      token_type: "Bearer",
      expires_in: 3600,
    };
    postMock.mockResolvedValueOnce(ok(tokens));
    await expect(refresh({ refresh_token: "rt" })).resolves.toEqual(tokens);
    expect(postMock).toHaveBeenCalledWith("/v1/auth/refresh", {
      body: { refresh_token: "rt" },
    });
  });

  it("forgotPassword POSTs /v1/auth/password/forgot", async () => {
    postMock.mockResolvedValueOnce(ok({}));
    await forgotPassword({ email: "a@b.test" });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/password/forgot", {
      body: { email: "a@b.test" },
    });
  });

  it("resetPassword POSTs /v1/auth/password/reset", async () => {
    postMock.mockResolvedValueOnce(ok({}));
    await resetPassword({
      email: "a@b.test",
      code: "123456",
      new_password: "Passw0rd!Passw0rd",
    });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/password/reset", {
      body: {
        email: "a@b.test",
        code: "123456",
        new_password: "Passw0rd!Passw0rd",
      },
    });
  });

  it("changePassword POSTs /v1/auth/change-password", async () => {
    postMock.mockResolvedValueOnce(ok({}));
    await changePassword({
      old_password: "Old1!Old1!Old1!",
      new_password: "New1!New1!New1!",
    });
    expect(postMock).toHaveBeenCalledWith("/v1/auth/change-password", {
      body: {
        old_password: "Old1!Old1!Old1!",
        new_password: "New1!New1!New1!",
      },
    });
  });

  it("logout POSTs /v1/auth/logout with no body", async () => {
    postMock.mockResolvedValueOnce(ok({}));
    await logout();
    expect(postMock).toHaveBeenCalledWith("/v1/auth/logout", {});
  });

  it("getMe GETs /v1/me and returns MeResponse", async () => {
    const me = { user_id: "u-1", email: "a@b.test", display_name: "A" };
    getMock.mockResolvedValueOnce(ok(me));
    await expect(getMe()).resolves.toEqual(me);
    expect(getMock).toHaveBeenCalledWith("/v1/me", {});
  });

  it("patchMe PATCHes /v1/me with the body and returns MeResponse", async () => {
    const me = { user_id: "u-1", email: "a@b.test", display_name: "B" };
    patchMock.mockResolvedValueOnce(ok(me));
    await expect(patchMe({ display_name: "B" })).resolves.toEqual(me);
    expect(patchMock).toHaveBeenCalledWith("/v1/me", {
      body: { display_name: "B" },
    });
  });
});

describe("auth endpoints — error mapping", () => {
  beforeEach(() => {
    postMock.mockReset();
    getMock.mockReset();
    patchMock.mockReset();
  });

  it("expectData → ApiError when fetch returns an error body", async () => {
    postMock.mockResolvedValueOnce(fail(401, { code: "auth.invalid_credentials" }));
    await expect(login({ email: "a@b.test", password: "x" })).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      detail: { code: "auth.invalid_credentials" },
      message: "POST /v1/auth/login failed: 401",
    });
  });

  it("expectData → ApiError with null detail when data is undefined", async () => {
    postMock.mockResolvedValueOnce(undef(204));
    await expect(
      register({
        email: "a@b.test",
        password: "Passw0rd!Passw0rd",
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 204,
      detail: null,
    });
  });

  it("expectVoid → ApiError when fetch returns an error body", async () => {
    postMock.mockResolvedValueOnce(fail(422, { code: "validation.request_invalid" }));
    await expect(confirmSignup({ email: "a@b.test", code: "wrong" })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: { code: "validation.request_invalid" },
    });
  });

  it("expectVoid resolves when there is no error, even with undefined data", async () => {
    postMock.mockResolvedValueOnce(undef(204));
    await expect(logout()).resolves.toBeUndefined();
  });

  it("GET endpoints surface ApiError on failure", async () => {
    getMock.mockResolvedValueOnce(fail(401, { code: "auth.token_expired" }));
    await expect(getMe()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
  });

  it("PATCH endpoints surface ApiError on failure", async () => {
    patchMock.mockResolvedValueOnce(fail(422, { code: "validation.request_invalid" }));
    await expect(patchMe({ display_name: "" })).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
    });
  });
});
