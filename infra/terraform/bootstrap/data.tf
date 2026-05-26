data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# AWS-managed CloudFront policies. Looking them up by name (instead of
# hardcoding the documented UUIDs) makes the config robust to AWS ID
# rotation and self-documenting.
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host_header" {
  name = "Managed-AllViewerExceptHostHeader"
}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Bucket names must be globally unique across all AWS. Appending the
  # account id guarantees uniqueness without random_id non-determinism.
  tf_state_bucket_name = "nica-erp-tf-state-${local.account_id}"
  web_bucket_name      = "nica-erp-web-${local.account_id}"
}
