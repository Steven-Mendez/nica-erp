# CloudFront /api/* origin swap.
#
# The bootstrap distribution declares an `/api/*` behavior pointing at
# `placeholder.invalid`. After `terraform apply` here, the ALB DNS
# replaces that placeholder so end users hitting
# `https://<dist>.cloudfront.net/api/*` reach the ECS service.
#
# Implementation note: AWS does not expose a clean "update one origin"
# API at the Terraform-resource level. The bootstrap root owns
# `aws_cloudfront_distribution.web` and would normally fight us over
# any change to its body.
#
# We resolve this in code (not Terraform) by having
# `scripts/deploy-web.sh` (`add-deploy-destroy-automation`) issue an
# `aws cloudfront update-distribution` call that patches only the
# `api-placeholder` origin's `DomainName` to the ALB DNS we expose
# below. This keeps Terraform ownership clean: bootstrap owns the
# distribution shape; the deploy script owns the origin-target swap.
#
# This file therefore only exposes the ALB DNS as an explicit output
# (also surfaced by module.compute.alb_dns_name) so the deploy script
# can read it from the env's outputs.
#
# If a future change wants to move the origin swap into Terraform,
# the pattern is `aws_cloudfront_distribution` with
# `lifecycle.ignore_changes` on every attribute the bootstrap owns
# (default_cache_behavior, origin[0] for S3, custom_error_response,
# viewer_certificate, aliases), changing only the
# api-placeholder origin's DomainName. Out of scope for sprint 01.

locals {
  cloudfront_distribution_id     = data.aws_cloudfront_distribution.bootstrap.id
  cloudfront_distribution_domain = data.aws_cloudfront_distribution.bootstrap.domain_name
}
