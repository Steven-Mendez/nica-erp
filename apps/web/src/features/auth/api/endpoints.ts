// apps/web/src/features/auth/api/endpoints.ts
//
// Identity / auth endpoints exposed as awaitable functions. Each wraps a
// single openapi-fetch call against the typed `paths` schema generated from
// `/openapi.json`. The shapes (RegisterRequest, TokenResponse, MeResponse,
// …) live in `@/api/schema` — no hand-written wire-type duplication.
//
// `ApiError` carries the parsed RFC-7807 problem-details body. Consumers can
// pipe it through `@/api/errors.ts`'s `mapProblemDetails` to decide between
// toast / form / redirect outcomes.
//
// Lives inside `features/auth/` so the slice owns its HTTP contract; only
// shared infrastructure (typed client, interceptor, token store, problem
// mapper) stays in `src/api/`.

import { api } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export type RegisterInput = Schemas["RegisterRequest"];
export type ConfirmSignupInput = Schemas["ConfirmSignupRequest"];
export type ResendCodeInput = Schemas["ResendCodeRequest"];
export type LoginInput = Schemas["LoginRequest"];
export type RefreshInput = Schemas["RefreshRequest"];
export type ForgotPasswordInput = Schemas["ForgotPasswordRequest"];
export type ResetPasswordInput = Schemas["ResetPasswordRequest"];
export type ChangePasswordInput = Schemas["ChangePasswordRequest"];
export type UpdateMeInput = Schemas["UpdateMeRequest"];
export type TokenBundle = Schemas["TokenResponse"];
export type Me = Schemas["MeResponse"];

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(label: string, status: number, detail: unknown) {
    super(`${label} failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

const expectData = <T>(label: string, result: FetchResult<T>): T => {
  if (result.error !== undefined) {
    throw new ApiError(label, result.response.status, result.error);
  }
  if (result.data === undefined) {
    throw new ApiError(label, result.response.status, null);
  }
  return result.data;
};

const expectVoid = (label: string, result: FetchResult<unknown>): void => {
  if (result.error !== undefined) {
    throw new ApiError(label, result.response.status, result.error);
  }
};

// ---- unauthenticated -----------------------------------------------------

export const register = async (body: RegisterInput): Promise<Schemas["RegisterResponse"]> => {
  const result = await api.POST("/v1/auth/register", { body });
  return expectData("POST /v1/auth/register", result);
};

export const confirmSignup = async (body: ConfirmSignupInput): Promise<void> => {
  const result = await api.POST("/v1/auth/confirm-signup", { body });
  expectVoid("POST /v1/auth/confirm-signup", result);
};

export const resendCode = async (body: ResendCodeInput): Promise<void> => {
  const result = await api.POST("/v1/auth/resend-code", { body });
  expectVoid("POST /v1/auth/resend-code", result);
};

export const login = async (body: LoginInput): Promise<TokenBundle> => {
  const result = await api.POST("/v1/auth/login", { body });
  return expectData("POST /v1/auth/login", result);
};

export const refresh = async (body: RefreshInput): Promise<TokenBundle> => {
  const result = await api.POST("/v1/auth/refresh", { body });
  return expectData("POST /v1/auth/refresh", result);
};

export const forgotPassword = async (body: ForgotPasswordInput): Promise<void> => {
  const result = await api.POST("/v1/auth/password/forgot", { body });
  expectVoid("POST /v1/auth/password/forgot", result);
};

export const resetPassword = async (body: ResetPasswordInput): Promise<void> => {
  const result = await api.POST("/v1/auth/password/reset", { body });
  expectVoid("POST /v1/auth/password/reset", result);
};

// ---- authenticated -------------------------------------------------------

export const changePassword = async (body: ChangePasswordInput): Promise<void> => {
  const result = await api.POST("/v1/auth/change-password", { body });
  expectVoid("POST /v1/auth/change-password", result);
};

export const logout = async (): Promise<void> => {
  const result = await api.POST("/v1/auth/logout", {});
  expectVoid("POST /v1/auth/logout", result);
};

export const getMe = async (): Promise<Me> => {
  const result = await api.GET("/v1/me", {});
  return expectData("GET /v1/me", result);
};

export const patchMe = async (body: UpdateMeInput): Promise<Me> => {
  const result = await api.PATCH("/v1/me", { body });
  return expectData("PATCH /v1/me", result);
};
