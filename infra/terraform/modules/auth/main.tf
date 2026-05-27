resource "aws_cognito_user_pool" "this" {
  name = var.name_prefix

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  # custom:active_tenant declared on day one so later sprints can write
  # it without forcing a User Pool recreation (Cognito attribute schema
  # is immutable).
  schema {
    name                     = "active_tenant"
    attribute_data_type      = "String"
    mutable                  = true
    developer_only_attribute = false
    required                 = false

    string_attribute_constraints {
      min_length = 0
      max_length = 64
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = merge(var.tags, { Name = var.name_prefix })
}

resource "aws_cognito_user_pool_client" "spa" {
  name         = "${var.name_prefix}-spa"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  # The SPA does NOT call Cognito directly — the API forwards
  # credentials over HTTPS via AdminInitiateAuth-equivalent flows.
  # USER_PASSWORD_AUTH must be enabled on the client for the API to
  # use it. SRP is intentionally omitted (MVP). ADR-0020.
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true

  # Hosted UI is NOT used in the MVP; callback URL is a placeholder
  # the SPA will not actually navigate to. ADR-0020.
  callback_urls = ["https://example.invalid/callback"]

  prevent_user_existence_errors = "ENABLED"

  # Token TTLs pinned to docs/06-security-model.md §TTLs. Minutes-based
  # units chosen to avoid Cognito's region-dependent defaults.
  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}
