// apps/web/src/api/tokenStore.ts
//
// In-memory-only token store.
//
// Transport-layer concern: the tokens live here (not in any feature) because
// they're consumed by the HTTP interceptor — every authenticated request, in
// any feature, picks them up. Holding them in a module-scoped closure (NOT
// localStorage / sessionStorage / cookies) is an explicit XSS-posture choice:
// if an attacker pulls off a script injection, they cannot exfiltrate a
// long-lived token from `window.localStorage`. The trade-off is that a page
// reload drops the session and the user has to log in again, which the
// frontend-shell spec requires.

export interface Tokens {
  readonly access: string;
  readonly refresh: string;
  readonly id: string;
}

let tokens: Tokens | null = null;

export const getAccessToken = (): string | null => tokens?.access ?? null;

export const getRefreshToken = (): string | null => tokens?.refresh ?? null;

export const getIdToken = (): string | null => tokens?.id ?? null;

export const setTokens = (next: Tokens): void => {
  tokens = { access: next.access, refresh: next.refresh, id: next.id };
};

export const clear = (): void => {
  tokens = null;
};
