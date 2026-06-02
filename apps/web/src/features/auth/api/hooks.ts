// apps/web/src/features/auth/api/hooks.ts
//
// TanStack Query bindings for the identity / auth endpoints. They sit on top
// of `./endpoints` (the typed wrappers) and `@/api/tokenStore` (the in-memory
// token store). Side effects on success / settled — storing tokens, busting
// the /me cache, clearing on logout — live here so every consumer of these
// hooks gets the same behaviour without per-route plumbing.
//
// `useMeQuery` is disabled when the in-memory access token is null so that
// the unauthenticated state does not trigger an immediate /v1/me request, per
// the frontend-shell spec.

import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
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
  type ChangePasswordInput,
  type ConfirmSignupInput,
  type ForgotPasswordInput,
  type LoginInput,
  type Me,
  type RefreshInput,
  type RegisterInput,
  type ResendCodeInput,
  type ResetPasswordInput,
  type TokenBundle,
  type UpdateMeInput,
} from "./endpoints";
import { clear, getAccessToken, setTokens } from "@/api/tokenStore";
import { clearPickerConfirmed } from "@/lib/route-guard";

export const meQueryKey = ["auth", "me"] as const;

export const useMeQuery = (): UseQueryResult<Me, Error> => {
  return useQuery<Me, Error>({
    queryKey: meQueryKey,
    queryFn: getMe,
    enabled: getAccessToken() !== null,
    staleTime: 30_000,
  });
};

const storeTokens = (bundle: TokenBundle): void => {
  setTokens({
    access: bundle.access_token,
    refresh: bundle.refresh_token,
    id: bundle.id_token,
  });
};

export const useLoginMutation = () => {
  const qc = useQueryClient();
  return useMutation<TokenBundle, Error, LoginInput>({
    mutationFn: login,
    onSuccess: (bundle) => {
      storeTokens(bundle);
      void qc.invalidateQueries({ queryKey: meQueryKey });
    },
  });
};

export const useRefreshMutation = () => {
  return useMutation<TokenBundle, Error, RefreshInput>({
    mutationFn: refresh,
    onSuccess: storeTokens,
  });
};

export const useRegisterMutation = () => {
  return useMutation<{ message?: string }, Error, RegisterInput>({
    mutationFn: register,
  });
};

export const useConfirmSignupMutation = () => {
  const qc = useQueryClient();
  return useMutation<TokenBundle | null, Error, ConfirmSignupInput>({
    mutationFn: confirmSignup,
    onSuccess: (bundle) => {
      // When the request carried a password the backend returns tokens;
      // store them and refresh /me so the route guard can route the
      // user to the right step (welcome / onboarding / tenants /
      // dashboard) without a forced /login round-trip.
      if (bundle != null) {
        storeTokens(bundle);
        void qc.invalidateQueries({ queryKey: meQueryKey });
      }
    },
  });
};

export const useResendCodeMutation = () => {
  return useMutation<void, Error, ResendCodeInput>({
    mutationFn: resendCode,
  });
};

export const useForgotPasswordMutation = () => {
  return useMutation<void, Error, ForgotPasswordInput>({
    mutationFn: forgotPassword,
  });
};

export const useResetPasswordMutation = () => {
  return useMutation<void, Error, ResetPasswordInput>({
    mutationFn: resetPassword,
  });
};

export const useChangePasswordMutation = () => {
  return useMutation<void, Error, ChangePasswordInput>({
    mutationFn: changePassword,
  });
};

export const useLogoutMutation = () => {
  const qc = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: logout,
    onSettled: () => {
      clear();
      clearPickerConfirmed();
      qc.clear();
    },
  });
};

export const useUpdateMeMutation = () => {
  const qc = useQueryClient();
  return useMutation<Me, Error, UpdateMeInput>({
    mutationFn: patchMe,
    onSuccess: (next) => {
      qc.setQueryData(meQueryKey, next);
    },
  });
};
