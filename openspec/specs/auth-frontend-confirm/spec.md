# auth-frontend-confirm Specification

## Purpose
TBD - created by archiving change add-confirm-otp-slot-input. Update Purpose after archive.
## Requirements
### Requirement: Verification code field renders six slots

The `/confirm` route SHALL render the verification-code input as
six discrete slot elements via the shadcn `input-otp` primitive,
not as a single `<input>` text field. Exactly six slots MUST be
rendered, indexed `0..5`, grouped under a single
`<InputOTPGroup>` with no separators. The primitive MUST be
imported from `@/components/ui/input-otp`.

#### Scenario: Six slots visible on mount

- **WHEN** an unauthenticated user navigates to `/confirm`
- **THEN** the rendered DOM contains exactly six elements with
  `data-slot="input-otp-slot"` (or equivalent slot marker
  emitted by the shadcn primitive), each empty

#### Scenario: No separator between slots

- **WHEN** the `/confirm` route DOM is inspected
- **THEN** no `<InputOTPSeparator>` (or equivalent
  `data-slot="input-otp-separator"`) element is present between
  the six slots

### Requirement: Field captures exactly six numeric characters

The verification-code field SHALL accept at most six characters
of input. The underlying `<InputOTP>` MUST be configured with
`maxLength={6}`, and the field value SHALL be bound through the
existing React Hook Form `Controller` so that
`confirmSchema.code` (six-digit Zod constraint) runs on submit
and on change as before.

#### Scenario: Typing seven digits truncates to six

- **WHEN** the user types "1234567" into the OTP field
- **THEN** the controlled value held by the form is "123456"
  and the seventh character is dropped

#### Scenario: Submitting a 6-digit code triggers confirmSignup

- **WHEN** the user fills all six slots with digits and submits
  the form
- **THEN** `useConfirmSignupMutation().mutate` is called with
  `{ email, code }` where `code` is the assembled six-character
  string

#### Scenario: Submitting fewer than six digits surfaces a Zod error

- **WHEN** the user submits the form with only "123" in the OTP
  field
- **THEN** no mutation is fired and the existing `<FieldError>`
  renders the `confirmSchema` validation message

### Requirement: Paste distributes digits across slots

The OTP component SHALL accept a six-character clipboard paste
into any focused slot and SHALL distribute the characters
across the six slots in order, updating the controlled form
value to the pasted string. Non-numeric pasted strings MUST be
rejected by the underlying `input-otp` package's numeric
pattern.

#### Scenario: Paste of "654321" fills every slot

- **WHEN** the user focuses slot 0 and pastes the clipboard
  string "654321"
- **THEN** slots 0..5 display "6", "5", "4", "3", "2", "1"
  respectively and the controlled form value is "654321"

### Requirement: SMS one-time-code autofill is preserved

The underlying hidden input that backs the `<InputOTP>` SHALL
carry `autoComplete="one-time-code"` and
`inputMode="numeric"` so iOS Safari and Android Chrome surface
the SMS-autofill chip and the numeric keypad on mobile. The
implementation MUST NOT override these attributes downstream.

#### Scenario: Hidden input exposes one-time-code autocomplete

- **WHEN** the `/confirm` page is rendered and the OTP root is
  inspected
- **THEN** the underlying input element carries
  `autocomplete="one-time-code"` and `inputmode="numeric"`

### Requirement: Field label and error wiring remain intact

The OTP composition SHALL remain inside the existing
`<Field data-invalid={…}>` / `<FieldLabel htmlFor="code">` /
`<FieldError>` slots so that screen-reader semantics
(`aria-invalid`, `aria-describedby` via `FieldError`) and the
shadcn invalid-state styling match the email field above. The
label text MUST stay in Spanish: `Código de verificación`.

#### Scenario: Label points at the OTP root

- **WHEN** the rendered page is queried by
  `getByLabelText("Código de verificación")`
- **THEN** the resolved element is the OTP root (or the hidden
  input the primitive uses for label association)

#### Scenario: Submission with invalid code marks the field aria-invalid

- **WHEN** the user submits with a non-six-digit code and Zod
  validation fails
- **THEN** the `<Field>` carries `data-invalid="true"` and the
  underlying input carries `aria-invalid="true"`

### Requirement: User-facing strings remain in Spanish

Every visible string on `/confirm` SHALL remain in Spanish.
Specifically, the field label `Código de verificación`, the
page heading `Confirma tu correo`, the help copy `Ingresa el
código de 6 dígitos que enviamos a tu correo`, and the
button labels `Confirmar` / `Reenviar código` SHALL NOT be
changed by this migration. The OTP primitive MUST NOT introduce
any English placeholder, helper text, or aria-label.

#### Scenario: Slots carry no English helper text

- **WHEN** the `/confirm` page DOM is inspected
- **THEN** no slot carries an `aria-label`, `title`, or visible
  text containing English words such as "digit", "code", or
  "OTP"
