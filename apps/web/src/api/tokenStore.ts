// apps/web/src/api/tokenStore.ts
//
// Hybrid token store.
//
// Transport-layer concern: the tokens live here (not in any feature) because
// they're consumed by the HTTP interceptor — every authenticated request, in
// any feature, picks them up.
//
// Storage strategy:
//   - Access AND id tokens stay in JavaScript memory only (module-scoped
//     closure). They are short-lived (≤ 1 hour) and never persisted.
//   - The refresh token is persisted in `sessionStorage` so a page reload can
//     recover the session via `POST /v1/auth/refresh` (see `bootRefresh` in
//     `@/api/interceptor`). sessionStorage is tab-scoped — closing the tab
//     still requires a fresh login.
//
// XSS posture: an attacker with script execution can still exfiltrate the
// refresh token from sessionStorage. HttpOnly cookies + a BFF remain the
// post-MVP hardening. The trade-off is deliberate: forcing a re-login on
// every reload was a UX blocker for operators.

const STORAGE_KEY = "nica-erp:refresh-token";

export interface Tokens {
  readonly access: string;
  readonly refresh: string;
  readonly id: string;
}

const readPersistedRefresh = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
};

const writePersistedRefresh = (value: string): void => {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    // sessionStorage can throw in private windows or when quota is exceeded.
    // The interceptor still works for the lifetime of this JS context; we
    // just lose reload-survival for this tab.
  }
};

const clearPersistedRefresh = (): void => {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Same as above.
  }
};

let accessToken: string | null = null;
let idToken: string | null = null;
let refreshToken: string | null = readPersistedRefresh();

export const getAccessToken = (): string | null => accessToken;

export const getRefreshToken = (): string | null => refreshToken;

export const getIdToken = (): string | null => idToken;

export const setTokens = (next: Tokens): void => {
  accessToken = next.access;
  refreshToken = next.refresh;
  idToken = next.id;
  writePersistedRefresh(next.refresh);
};

export const clear = (): void => {
  accessToken = null;
  refreshToken = null;
  idToken = null;
  clearPersistedRefresh();
};
