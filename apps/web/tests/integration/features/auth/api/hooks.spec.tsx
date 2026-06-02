// Unit tests for the auth TanStack Query hooks. Stubs `./endpoints`
// so each hook is exercised in isolation; the focus is on the
// side-effect logic (setTokens on login/refresh, cache invalidation,
// clear + picker-flag clear on logout).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/features/auth/api/endpoints", () => ({
  login: vi.fn(),
  refresh: vi.fn(),
  register: vi.fn(),
  confirmSignup: vi.fn(),
  resendCode: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn(),
  patchMe: vi.fn(),
  getMe: vi.fn(),
}));

vi.mock("@/api/tokenStore", () => ({
  setTokens: vi.fn(),
  clear: vi.fn(),
  getAccessToken: vi.fn().mockReturnValue("access-token"),
}));

import {
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
import { clear, setTokens } from "@/api/tokenStore";
import { PICKER_FLAG_KEY } from "@/lib/route-guard";
import {
  meQueryKey,
  useChangePasswordMutation,
  useConfirmSignupMutation,
  useForgotPasswordMutation,
  useLoginMutation,
  useLogoutMutation,
  useMeQuery,
  useRefreshMutation,
  useRegisterMutation,
  useResendCodeMutation,
  useResetPasswordMutation,
  useUpdateMeMutation,
} from "@/features/auth/api/hooks";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("auth queries", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useMeQuery calls getMe when an access token is present", async () => {
    vi.mocked(getMe).mockResolvedValueOnce({
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      preferences: {},
      active_tenant: null,
      role: null,
      permissions: [],
    } as Awaited<ReturnType<typeof getMe>>);
    const client = makeClient();
    const { result } = renderHook(() => useMeQuery(), { wrapper: wrapper(client) });
    await waitFor(() => expect(result.current.data?.id).toBe("u-1"));
  });
});

describe("auth mutations — token-bundle hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const bundle = {
    access_token: "a",
    refresh_token: "r",
    id_token: "i",
    token_type: "Bearer" as const,
  };

  it("useLoginMutation stores tokens and invalidates meQueryKey on success", async () => {
    vi.mocked(login).mockResolvedValueOnce(bundle);
    const client = makeClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useLoginMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com", password: "secret" });
    expect(setTokens).toHaveBeenCalledWith({ access: "a", refresh: "r", id: "i" });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: meQueryKey });
  });

  it("useRefreshMutation stores tokens on success", async () => {
    vi.mocked(refresh).mockResolvedValueOnce(bundle);
    const client = makeClient();
    const { result } = renderHook(() => useRefreshMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ refresh_token: "old" });
    expect(setTokens).toHaveBeenCalledWith({ access: "a", refresh: "r", id: "i" });
  });
});

describe("auth mutations — simple wrappers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("useRegisterMutation calls register endpoint", async () => {
    vi.mocked(register).mockResolvedValueOnce({});
    const client = makeClient();
    const { result } = renderHook(() => useRegisterMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com", password: "secret" });
    expect(vi.mocked(register).mock.calls[0]?.[0]).toEqual({
      email: "x@y.com",
      password: "secret",
    });
  });

  it("useConfirmSignupMutation calls confirmSignup", async () => {
    vi.mocked(confirmSignup).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const { result } = renderHook(() => useConfirmSignupMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com", code: "123456" });
    expect(vi.mocked(confirmSignup).mock.calls[0]?.[0]).toEqual({
      email: "x@y.com",
      code: "123456",
    });
  });

  it("useResendCodeMutation calls resendCode", async () => {
    vi.mocked(resendCode).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const { result } = renderHook(() => useResendCodeMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com" });
    expect(vi.mocked(resendCode).mock.calls[0]?.[0]).toEqual({ email: "x@y.com" });
  });

  it("useForgotPasswordMutation calls forgotPassword", async () => {
    vi.mocked(forgotPassword).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const { result } = renderHook(() => useForgotPasswordMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com" });
    expect(vi.mocked(forgotPassword).mock.calls[0]?.[0]).toEqual({ email: "x@y.com" });
  });

  it("useResetPasswordMutation calls resetPassword", async () => {
    vi.mocked(resetPassword).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const { result } = renderHook(() => useResetPasswordMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ email: "x@y.com", code: "123456", new_password: "Newpw1!" });
    expect(resetPassword).toHaveBeenCalled();
  });

  it("useChangePasswordMutation calls changePassword", async () => {
    vi.mocked(changePassword).mockResolvedValueOnce(undefined as never);
    const client = makeClient();
    const { result } = renderHook(() => useChangePasswordMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({
      old_password: "Oldpw1!",
      new_password: "Newpw1!",
    });
    expect(changePassword).toHaveBeenCalled();
  });
});

describe("useLogoutMutation", () => {
  it("clears the token store, the picker flag, and the entire query cache", async () => {
    vi.mocked(logout).mockResolvedValueOnce(undefined as never);
    window.sessionStorage.setItem(PICKER_FLAG_KEY, "1");
    const client = makeClient();
    const clearSpy = vi.spyOn(client, "clear");
    const { result } = renderHook(() => useLogoutMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync();
    expect(clear).toHaveBeenCalled();
    expect(window.sessionStorage.getItem(PICKER_FLAG_KEY)).toBeNull();
    expect(clearSpy).toHaveBeenCalled();
  });
});

describe("useUpdateMeMutation", () => {
  it("sets the me query data on success", async () => {
    const me = {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada",
      preferences: {},
      active_tenant: null,
      role: null,
      permissions: [],
    } as Awaited<ReturnType<typeof patchMe>>;
    vi.mocked(patchMe).mockResolvedValueOnce(me);
    const client = makeClient();
    const { result } = renderHook(() => useUpdateMeMutation(), { wrapper: wrapper(client) });
    await result.current.mutateAsync({ display_name: "Ada" });
    expect(client.getQueryData(meQueryKey)).toEqual(me);
  });
});
