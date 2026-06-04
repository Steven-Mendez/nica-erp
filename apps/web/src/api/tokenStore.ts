// apps/web/src/api/tokenStore.ts
//
// In-memory token store.
//
// Transport-layer concern: the tokens live here (not in any feature) because
// they're consumed by the HTTP interceptor — every authenticated request, in
// any feature, picks them up.
//
// Storage strategy:
//   - Access AND id tokens stay in JavaScript memory only (module-scoped
//     closure). They are short-lived (≤ 1 hour) and never persisted.
//   - The refresh token does NOT live in JavaScript at all. The API sets
//     it via the `nica_erp_rt` httpOnly cookie; the SPA only needs to send
//     `credentials: "include"` on the auth/refresh round-trip and the
//     browser handles the rest. A successful XSS therefore cannot read
//     or exfiltrate the refresh credential.

export interface Tokens {
  readonly access: string;
  readonly id: string;
}

let accessToken: string | null = null;
let idToken: string | null = null;

export const getAccessToken = (): string | null => accessToken;

export const getIdToken = (): string | null => idToken;

export const setTokens = (next: Tokens): void => {
  accessToken = next.access;
  idToken = next.id;
};

export const clear = (): void => {
  accessToken = null;
  idToken = null;
};
