// Mailpit helper for Playwright e2e fixtures.
//
// The local stack (`docker compose up` from `docker/`) runs Mailpit on
// :8025 (HTTP API + UI) and :1025 (SMTP). The API publisher uses the
// SMTP-bound `EmailSenderSmtp` adapter, so every signup / password
// reset / invitation email lands in Mailpit. Reading them back is the
// only way the fixtures can drive the SPA past `/confirm` without
// shortcutting through the API.
//
// MAILPIT_BASE_URL overrides the default (CI sets it to the service
// hostname).

const MAILPIT_BASE = process.env.MAILPIT_BASE_URL ?? "http://127.0.0.1:8025";

const SIX_DIGIT_CODE = /\b(\d{6})\b/;

interface MailpitMessageSummary {
  ID: string;
  To: { Address: string }[];
  Subject: string;
  Created: string;
}

interface MailpitMessage {
  ID: string;
  Text: string;
  HTML: string;
}

/**
 * Wait until Mailpit has at least one message addressed to `email`
 * that was created after `since`, then return its body.
 */
export async function waitForEmail(opts: {
  email: string;
  since: Date;
  subjectIncludes?: string;
  timeoutMs?: number;
}): Promise<MailpitMessage> {
  const timeoutMs = opts.timeoutMs ?? 15_000;
  const deadline = Date.now() + timeoutMs;
  let lastError = "no email matched";
  while (Date.now() < deadline) {
    const res = await fetch(
      `${MAILPIT_BASE}/api/v1/search?query=${encodeURIComponent(`to:${opts.email}`)}`,
    );
    if (res.ok) {
      const body = (await res.json()) as { messages: MailpitMessageSummary[] };
      const match = body.messages.find((m) => {
        if (new Date(m.Created) < opts.since) return false;
        if (opts.subjectIncludes && !m.Subject.includes(opts.subjectIncludes)) return false;
        return m.To.some((t) => t.Address.toLowerCase() === opts.email.toLowerCase());
      });
      if (match) {
        const full = await fetch(`${MAILPIT_BASE}/api/v1/message/${match.ID}`);
        if (full.ok) return (await full.json()) as MailpitMessage;
        lastError = `fetch ${match.ID} returned ${full.status}`;
      }
    } else {
      lastError = `search returned ${res.status}`;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`waitForEmail(${opts.email}): ${lastError}`);
}

/** Extract the first six-digit code from a message body. */
export function extractOtp(message: MailpitMessage): string {
  const haystack = message.Text || message.HTML;
  const match = SIX_DIGIT_CODE.exec(haystack);
  const code = match?.[1];
  if (!code) throw new Error(`no 6-digit code in body: ${haystack.slice(0, 200)}`);
  return code;
}

/** Extract the invitation token from an invite email body. */
export function extractInviteToken(message: MailpitMessage): string {
  const haystack = message.Text || message.HTML;
  const match = /\/invitations\/accept#t=([A-Za-z0-9_\-.]+)/.exec(haystack);
  const token = match?.[1];
  if (!token) throw new Error(`no invite token in body: ${haystack.slice(0, 200)}`);
  return token;
}

/**
 * Reset the Mailpit inbox. Use sparingly — most fixtures should filter
 * by `since` instead so concurrent tests don't trample each other.
 */
export async function clearMailpit(): Promise<void> {
  const res = await fetch(`${MAILPIT_BASE}/api/v1/messages`, { method: "DELETE" });
  if (!res.ok) throw new Error(`clearMailpit: ${res.status}`);
}
