# add-backend-test-quality-guards

Sprint follow-up — Backend test triad gains defect-finding guards on
top of the in-flight coverage backfill. Hypothesis-driven property
tests search the input space of every domain value object; a
schema-vs-repository consistency test catches schema drift on day one;
a direct RLS-policy enforcement test verifies the Postgres policy at
the database layer (not just the HTTP middleware); a
`tests/_factories/` package supplies canonical domain builders and
RLS-compliant DB seeders; three Makefile lanes (`test-be-unit`,
`test-be-integration`, `test-be-e2e`) split the triad so the cheapest
layer runs without a testcontainer.

Outcome at close: 285 backend tests, all three lanes green
(186 unit / 89 integration / 10 e2e). Durable spec under
[`openspec/specs/backend-test-quality-guards/spec.md`](../../../specs/backend-test-quality-guards/spec.md).
