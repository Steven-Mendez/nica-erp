// Read-once, in-memory hand-off for the password typed on `/signup` so
// `/confirm` can finish the signup with `POST /v1/auth/confirm-signup`
// carrying the password (200 + tokens), removing the forced re-login
// after the email code. The value lives only in JS memory: a hard
// reload of `/confirm` clears it and the route falls back to its
// historical "navigate to /login after confirm" behaviour.
//
// We deliberately do NOT use sessionStorage / localStorage / history
// state for this: the project keeps tokens and credentials out of
// browser storage to shrink the XSS blast radius (see token store
// notes in `apps/web/src/api/tokenStore.ts`).

let pending: string | null = null;

export const stashSignupPassword = (password: string): void => {
  pending = password;
};

export const popSignupPassword = (): string | null => {
  const value = pending;
  pending = null;
  return value;
};

export const clearSignupPassword = (): void => {
  pending = null;
};
