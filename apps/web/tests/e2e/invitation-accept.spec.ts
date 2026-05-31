// Invitation accept (stash flow): an owner invites a brand-new user;
// the invitee opens the invitation deep link BEFORE signing up; the
// SPA previews the invitation, stashes the token in sessionStorage,
// redirects to /signup with the email pre-filled, walks the invitee
// through signup → confirm → login, and the post-login bootstrap pops
// the stash and lands the invitee on the empresa A dashboard.
//
// This complements `member-management.spec.ts` which exercises the
// other entry path (invitee signs up first, then opens the deep link
// as an authenticated user). The stash branch is what fires when
// someone clicks an invitation email link without an existing Nica
// ERP account.
//
// ⚠ Marked `.fixme()` while a known SPA bug in the stash path is open:
// after a successful POST /v1/invitations/accept (200) the route's
// `navigate({ to: "/dashboard" })` in `AcceptInvitationRoute`'s
// mutate-level onSuccess does not take effect; the SPA stays stuck on
// `/invitations/accept` rendering "Aceptando…". The same accept POST
// works fine when the invitee is already authenticated before opening
// the link (covered by member-management.spec.ts). The backend state
// is good — the membership is created — but the SPA never advances.
// When the SPA fix lands, flip `.fixme` back to `test` and remove
// this preamble.

import { expect, test } from "@playwright/test";

import {
  E2E_PASSWORD,
  signupConfirmLogin,
  uniqueEmail,
} from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";
import { extractOtp, waitForEmail } from "./fixtures/mailpit";

test.describe("invitation accept (stash flow) @critical", () => {
  test(
    "invitee opens link first, signs up, lands in the inviter's empresa",
    async ({ browser }) => {
      // ── Owner: sign up, create empresa A, invite a new email. ───────
      const ownerContext = await browser.newContext();
      const ownerPage = await ownerContext.newPage();
      const inviteeEmail = uniqueEmail("stash-invitee");

      await signupConfirmLogin(ownerPage);
      const { name: empresaName } = await createEmpresa(ownerPage);
      const { token } = await inviteMember(ownerPage, {
        email: inviteeEmail,
        role: "accountant",
      });

      // ── Invitee: anonymous browser context, opens the deep link. ────
      const inviteeContext = await browser.newContext();
      const inviteePage = await inviteeContext.newPage();

      // Hit the accept route BEFORE signing up. The SPA should preview
      // the invitation, stash the token in sessionStorage, and
      // redirect to /signup with the invitee email pre-filled.
      const before = new Date(Date.now() - 1_000);
      await inviteePage.goto(`/invitations/accept#t=${token}`);
      await inviteePage.waitForURL(/\/signup/);
      await expect(inviteePage.getByLabel(/Correo/i)).toHaveValue(
        inviteeEmail,
      );

      // ── Invitee: complete signup → confirm → login inline. ──────────
      await inviteePage
        .getByLabel("Contraseña", { exact: true })
        .fill(E2E_PASSWORD);
      await inviteePage
        .getByLabel("Confirmar contraseña")
        .fill(E2E_PASSWORD);
      await inviteePage.getByRole("button", { name: /Crear cuenta/i }).click();
      await inviteePage.waitForURL(/\/confirm/);

      const confirmEmail = await waitForEmail({
        email: inviteeEmail,
        since: before,
        subjectIncludes: "confirma",
      });
      const otp = extractOtp(confirmEmail);
      await inviteePage
        .locator("input[autocomplete='one-time-code']")
        .first()
        .focus();
      await inviteePage.keyboard.type(otp);
      await inviteePage.getByRole("button", { name: /^Confirmar$/i }).click();
      await inviteePage.waitForURL(/\/login/);

      await inviteePage.locator("input#email").fill(inviteeEmail);
      await inviteePage.locator("input#password").fill(E2E_PASSWORD);
      await inviteePage
        .getByRole("button", { name: /Iniciar sesión/i })
        .click();

      // ── Bootstrap: pops the stash, redeems the invitation. The
      //    invitee transits /dashboard briefly (proving the bug-fixed
      //    accept flow is unblocked), then the post-accept route
      //    guards fire in this order:
      //      1. display_name still null (stash flow skipped /welcome)
      //         → /welcome
      //      2. After /welcome, `active_tenant` is still null on the
      //         JWT (the accept POST does not rotate tokens), so the
      //         guard's defensive fallback ships them to /tenants
      //      3. The invitee picks the (only) empresa to land on
      //         /dashboard for real.
      //    The intermediate trips through /welcome and /tenants are
      //    existing UX, not the bug under test.
      await inviteePage.waitForLoadState("networkidle");
      if (/\/welcome/.test(inviteePage.url())) {
        await inviteePage.getByLabel(/Nombre/i).fill("Stash Invitee");
        await inviteePage
          .getByRole("button", { name: /Continuar|Guardar/i })
          .click();
      }
      await inviteePage.waitForURL(/\/tenants(\?|$)/);
      // Pick the (only) empresa — the row is keyed by the empresa name.
      await inviteePage.getByText(empresaName).first().click();
      await inviteePage.waitForURL(/\/dashboard/);
      await expect(
        inviteePage.getByRole("combobox", { name: /Empresa activa/i }),
      ).toContainText(empresaName);

      // ── Owner sees the invitee promoted from pending to member. ─────
      await ownerPage.goto("/empresa/users");
      await expect(ownerPage.getByText(inviteeEmail)).toBeVisible();
      await expect(
        ownerPage.getByRole("cell", { name: /Contador/i }).first(),
      ).toBeVisible();

      await ownerContext.close();
      await inviteeContext.close();
    },
  );
});
