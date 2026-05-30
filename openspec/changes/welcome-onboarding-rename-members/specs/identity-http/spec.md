## MODIFIED Requirements

### Requirement: `GET /v1/me` SHALL serialise profile fields as nullable strings

The response schema of `GET /v1/me` SHALL declare `display_name: string | null`, `locale: string | null`, and `timezone: string | null`. The handler SHALL serialise `None` Python values as JSON `null`. The OpenAPI schema for `MeResponse` SHALL include `nullable: true` (or the OpenAPI 3.1 `null` union) on the three fields.

#### Scenario: `/v1/me` for a fresh user returns NULL for the three profile fields

- **GIVEN** a user who just confirmed signup and has not yet visited `/welcome`
- **WHEN** the SPA calls `GET /v1/me` with their bearer token
- **THEN** the response body SHALL include `"display_name": null`, `"locale": null`, and `"timezone": null`

#### Scenario: `/v1/me` for a completed profile returns string values

- **GIVEN** a user who has submitted `/welcome` with `display_name="Ada"` and `timezone="Europe/Madrid"`
- **WHEN** the SPA calls `GET /v1/me`
- **THEN** the response body SHALL include `"display_name": "Ada"`, `"timezone": "Europe/Madrid"`, and `"locale": null`

### Requirement: `PATCH /v1/me` SHALL accept partial profile updates with nullable fields

The `PATCH /v1/me` endpoint SHALL accept a request body in which `display_name`, `locale`, and `timezone` are each individually optional and individually nullable. Fields omitted from the body SHALL leave the corresponding column unchanged; fields explicitly set to `null` SHALL update the column to NULL.

#### Scenario: PATCH with only `display_name` and `timezone` populates those two

- **GIVEN** a user with all three profile fields `null`
- **WHEN** the SPA calls `PATCH /v1/me` with body `{"display_name": "Ada", "timezone": "Europe/Madrid"}`
- **THEN** the response SHALL be `204 No Content` and a subsequent `GET /v1/me` SHALL return `display_name="Ada"`, `timezone="Europe/Madrid"`, `locale=null`

#### Scenario: PATCH explicitly setting `display_name` to null clears it

- **GIVEN** a user with `display_name="Ada"`
- **WHEN** the SPA calls `PATCH /v1/me` with body `{"display_name": null}`
- **THEN** a subsequent `GET /v1/me` SHALL return `display_name=null`
