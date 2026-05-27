# S3 backend referenced to the bootstrap state bucket + lock table.
# Bucket name suffixes the account ID (see add-terraform-state-backend
# §2 — `nica-erp-tf-state-<account-id>`), so the operator must pass
# `bucket=nica-erp-tf-state-<account-id>` via `terraform init -backend-config="bucket=..."`
# the first time, OR the bucket name is templated in via a
# backend.hcl partial config. We accept the partial-config approach
# so this file stays account-agnostic and gitignore-free.

terraform {
  backend "s3" {
    key            = "envs/demo/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "nica-erp-tf-lock"
    encrypt        = true
    # bucket = supplied via `-backend-config="bucket=nica-erp-tf-state-<account>"`
  }
}
