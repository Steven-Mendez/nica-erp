// Invitation accept (stash flow): an owner invites a brand-new user;
// the invitee opens the invitation deep link BEFORE signing up; the
// SPA previews the invitation, stashes the token in sessionStorage,
// redirects to /signup with the email pre-filled, walks the invitee
// through signup → confirm (which auto-authenticates), then the
// guest-guard pops the stash, the invitations/accept route rotates
// the session, the welcome route captures the display name, and the
// invitee lands on the empresa A dashboard. No /login round-trip,
// no empresa-picker detour.
//
// This complements `member-management.spec.ts` which exercises the
// other entry path (invitee already had an account and opens the link
// authenticated).

import { expect, test } from "@playwright/test";

import { E2E_PASSWORD, signupConfirmLogin, uniqueEmail } from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";
import { extractOtp, waitForEmail } from "./fixtures/mailpit";

test.describe("invitation accept (stash flow) @critical", () => {
  test("invitee opens link first, signs up, lands in the inviter's empresa", async ({
    browser,
  }) => {
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

    // Hit the accept route BEFORE signing up. The SPA previews the
    // invitation, stashes the token in sessionStorage, and redirects
    // to /signup. Audit F-026: the preview deliberately does NOT
    // surface the invitee email, so the user types it themselves; the
    // backend's identity binding catches typos before any membership
    // row is written.
    const before = new Date(Date.now() - 1_000);
    await inviteePage.goto(`/invitations/accept#t=${token}`);
    await inviteePage.waitForURL(/\/signup/);

    // ── Invitee: complete signup → confirm (auto-authenticates). ────
    await inviteePage.getByLabel(/Correo/i).fill(inviteeEmail);
    await inviteePage.getByLabel("Contraseña", { exact: true }).fill(E2E_PASSWORD);
    await inviteePage.getByLabel("Confirmar contraseña").fill(E2E_PASSWORD);
    await inviteePage.getByRole("button", { name: /Crear cuenta/i }).click();
    await inviteePage.waitForURL(/\/confirm/);

    const confirmEmail = await waitForEmail({
      email: inviteeEmail,
      since: before,
      subjectIncludes: "confirma",
    });
    const otp = extractOtp(confirmEmail);
    await inviteePage.locator("input[autocomplete='one-time-code']").first().focus();
    await inviteePage.keyboard.type(otp);
    await inviteePage.getByRole("button", { name: /^Confirmar$/i }).click();

    // ── No /login round-trip: the confirm POST carries the password,
    //    the response is a session bundle, the guest-guard pops the
    //    stashed invite, /invitations/accept rotates tokens with the
    //    invited empresa baked in, the route guard sees display_name
    //    null and redirects to /welcome.
    await inviteePage.waitForURL(/\/welcome/);
    // Assert we never transited through /login.
    expect(inviteePage.url()).not.toContain("/login");
    await inviteePage.getByLabel(/Nombre/i).fill("Stash Invitee");
    await inviteePage.getByRole("button", { name: /Continuar|Guardar/i }).click();

    // ── After /welcome: active_tenant is already set by the
    //    invitation-accept's token rotation, so the route guard lets
    //    the user straight through to /dashboard without an
    //    empresa-picker detour at /tenants.
    await inviteePage.waitForURL(/\/dashboard/);
    expect(inviteePage.url()).not.toContain("/tenants");
    await expect(inviteePage.getByRole("button", { name: new RegExp(empresaName) })).toBeVisible();

    // ── Owner sees the invitee promoted from pending to member. ─────
    // Scope to the table since the email may also surface in other
    // sidebar/header chrome.
    await ownerPage.goto("/empresa/users");
    await expect(ownerPage.getByRole("table").getByText(inviteeEmail)).toBeVisible();
    await expect(ownerPage.getByRole("cell", { name: /Contador/i }).first()).toBeVisible();

    await ownerContext.close();
    await inviteeContext.close();
  });
});
