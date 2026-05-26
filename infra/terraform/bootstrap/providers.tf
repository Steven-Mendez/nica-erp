provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  # No default_tags: every taggable resource in this root sets the
  # Project tag explicitly, which avoids the first-plan diff that
  # default_tags produces on S3/ECR via the provider.
}
