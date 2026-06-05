# GitHub Actions OIDC federation for nica-erp.
#
# This file declares the AWS-side half of the CI auth chain consumed by
# .github/workflows/deploy.yml and .github/workflows/destroy.yml:
#
#   1. One aws_iam_openid_connect_provider for token.actions.githubusercontent.com
#      (AWS hard-limit: one per `url` per account).
#   2. Two narrowly-scoped IAM roles, one per workflow.
#
# Trust policy on every role binds the federated principal to
#   repo:Steven-Mendez/nica-erp:ref:refs/heads/main
# so feature-branch workflows cannot assume them. The day the team grows
# and auto-trigger on push lands, no trust-policy change is needed.

locals {
  github_owner_repo = "Steven-Mendez/nica-erp"
}

# ---- OIDC provider ----------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's OIDC issuer root thumbprint. AWS now validates the JWT chain
  # against the embedded root, so the thumbprint value is cosmetic — but
  # the field is still required by the API.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Project = "nica-erp"
  }
}

# ---- ci-deploy role ---------------------------------------------------------
#
# Assumed by .github/workflows/deploy.yml. Inline policy covers:
#   - ECR push (image build step)
#   - Terraform-state R/W (terraform apply on the ephemeral root)
#   - The ephemeral-stack apply surface (VPC, RDS, ECS, ALB, Cognito, SSM,
#     observability) — wildcards on the resource types because Terraform
#     creates/updates per-resource ARNs that don't exist yet at policy
#     creation time. The blast radius is bounded by the trust policy
#     (only refs/heads/main of this repo can assume) and by the
#     Project=nica-erp tag convention.
#   - SPA bucket put/delete + CloudFront invalidation (deploy-web step).
#
# Explicit Deny on the bootstrap-surface destructive actions.

data "aws_iam_policy_document" "ci_deploy_trust" {
  statement {
    sid     = "GitHubOIDCAssumeRoleDeploy"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_owner_repo}:ref:refs/heads/main"]
    }
  }
}

data "aws_iam_policy_document" "ci_deploy_permissions" {
  # ECR authorization token is account-scoped (AWS does not permit
  # resource scoping on this action).
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # ECR push + read, scoped to the nica-erp repository ARN. The read
  # actions (DescribeImages, ListImages, ListTagsForResource) are needed
  # by terraform's `data "aws_ecr_repository"` lookup in envs/demo:
  # recent AWS provider versions also fetch the most-recent-image
  # metadata and the repo's tag list.
  statement {
    sid    = "EcrPushNicaErp"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.api.arn]
  }

  # Terraform-state R/W: state bucket + lock table.
  statement {
    sid    = "TerraformStateRW"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.tf_state.arn,
      "${aws_s3_bucket.tf_state.arn}/*",
    ]
  }

  statement {
    sid    = "TerraformLockRW"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [aws_dynamodb_table.tf_lock.arn]
  }

  # The lock table is SSE-encrypted with a customer-managed CMK, so
  # any GetItem/PutItem also touches KMS. Without these grants the
  # backend lock acquisition fails with AccessDeniedException.
  statement {
    sid    = "TerraformLockCmk"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = [aws_kms_key.tf_lock.arn]
  }

  # SPA bucket put/delete (objects only, never the bucket itself).
  statement {
    sid    = "SpaBucketObjects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.web.arn,
      "${aws_s3_bucket.web.arn}/*",
    ]
  }

  # CloudFront read + invalidation for the bootstrap distribution.
  # GetDistribution + GetDistributionConfig + ListTagsForResource are
  # required by the `data "aws_cloudfront_distribution"` lookup in
  # envs/demo. UpdateDistribution is reserved for the future origin-swap
  # path documented in envs/demo/cloudfront_swap.tf.
  statement {
    sid    = "CloudFrontReadAndInvalidate"
    effect = "Allow"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:GetInvalidation",
      "cloudfront:ListTagsForResource",
      "cloudfront:UpdateDistribution",
    ]
    resources = [aws_cloudfront_distribution.web.arn]
  }

  # Ephemeral-stack apply surface. Terraform-managed resources do not
  # exist at policy creation time, so we scope by resource type rather
  # than ARN. The trust policy keeps the blast radius to refs/heads/main.
  statement {
    sid    = "EphemeralStackApply"
    effect = "Allow"
    actions = [
      "ec2:*",
      "rds:*",
      "ecs:*",
      "elasticloadbalancing:*",
      "logs:*",
      "cloudwatch:*",
      "ssm:*",
      "cognito-idp:*",
      "iam:PassRole",
      "iam:GetRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:TagRole",
      "iam:UntagRole",
      "sns:*",
      "application-autoscaling:*",
    ]
    resources = ["*"]
  }

  # Explicit Deny: bootstrap-surface destructive actions are out of
  # scope for deploy. ECR/CloudFront/state-bucket deletion belongs to
  # destroy-bootstrap (operator-host-only).
  statement {
    sid    = "DenyBootstrapDestructive"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "ecr:DeleteRepository",
      "cloudfront:DeleteDistribution",
      "cloudfront:DeleteOriginAccessControl",
      "iam:DeleteOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = ["*"]
  }

  # Explicit Deny on the CI roles themselves so a compromised deploy
  # session cannot rewrite its own policy or that of ci-destroy.
  statement {
    sid    = "DenyCiRoleMutation"
    effect = "Deny"
    actions = [
      "iam:DeleteRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/nica-erp-ci-deploy",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/nica-erp-ci-destroy",
    ]
  }
}

resource "aws_iam_role" "ci_deploy" {
  name                 = "nica-erp-ci-deploy"
  description          = "Assumed by .github/workflows/deploy.yml via OIDC. Scoped to ECR push, Terraform state R/W, ephemeral-stack apply, and SPA upload + CloudFront invalidation."
  assume_role_policy   = data.aws_iam_policy_document.ci_deploy_trust.json
  max_session_duration = 3600

  tags = {
    Project = "nica-erp"
  }
}

resource "aws_iam_role_policy" "ci_deploy" {
  name   = "nica-erp-ci-deploy-inline"
  role   = aws_iam_role.ci_deploy.id
  policy = data.aws_iam_policy_document.ci_deploy_permissions.json
}

# ---- ci-destroy role --------------------------------------------------------
#
# Assumed by .github/workflows/destroy.yml. Inline policy covers:
#   - The ephemeral-stack destroy surface (same resource types as
#     ci-deploy because terraform destroy needs to read+update before it
#     deletes).
#   - Terraform-state R/W.
#   - SPA bucket object cleanup (optional, gated by the workflow input).
# Explicit Deny on the bootstrap-surface destructive actions — only
# destroy-bootstrap (operator-host-only) can touch those.

data "aws_iam_policy_document" "ci_destroy_trust" {
  statement {
    sid     = "GitHubOIDCAssumeRoleDestroy"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_owner_repo}:ref:refs/heads/main"]
    }
  }
}

data "aws_iam_policy_document" "ci_destroy_permissions" {
  # Terraform-state R/W: terraform destroy reads + writes state.
  statement {
    sid    = "TerraformStateRW"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.tf_state.arn,
      "${aws_s3_bucket.tf_state.arn}/*",
    ]
  }

  statement {
    sid    = "TerraformLockRW"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
    ]
    resources = [aws_dynamodb_table.tf_lock.arn]
  }

  # Same CMK grant as ci-deploy; destroy must lock the state too.
  statement {
    sid    = "TerraformLockCmk"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = [aws_kms_key.tf_lock.arn]
  }

  # SPA bucket OBJECT cleanup only (workflow input clean_web_assets=true).
  # Note: no s3:DeleteBucket — that belongs to destroy-bootstrap.
  statement {
    sid    = "SpaBucketObjectCleanup"
    effect = "Allow"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.web.arn,
      "${aws_s3_bucket.web.arn}/*",
    ]
  }

  # Read-only access to the bootstrap ECR repo + CloudFront distribution.
  # terraform destroy still refreshes data sources before tearing the
  # ephemeral stack down, so these reads must succeed even though the
  # destroy role never pushes images or modifies the distribution.
  statement {
    sid    = "EcrReadNicaErp"
    effect = "Allow"
    actions = [
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
    ]
    resources = [aws_ecr_repository.api.arn]
  }

  statement {
    sid    = "CloudFrontRead"
    effect = "Allow"
    actions = [
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:ListTagsForResource",
    ]
    resources = [aws_cloudfront_distribution.web.arn]
  }

  # Ephemeral-stack destroy surface. Same scope as ci-deploy because
  # destroy needs read+update before it can delete.
  statement {
    sid    = "EphemeralStackDestroy"
    effect = "Allow"
    actions = [
      "ec2:*",
      "rds:*",
      "ecs:*",
      "elasticloadbalancing:*",
      "logs:*",
      "cloudwatch:*",
      "ssm:*",
      "cognito-idp:*",
      "iam:PassRole",
      "iam:GetRole",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:TagRole",
      "iam:UntagRole",
      "sns:*",
      "application-autoscaling:*",
    ]
    resources = ["*"]
  }

  # Explicit Deny: bootstrap-surface destructive actions stay
  # operator-host-only.
  statement {
    sid    = "DenyBootstrapDestructive"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "ecr:DeleteRepository",
      "cloudfront:DeleteDistribution",
      "cloudfront:DeleteOriginAccessControl",
      "iam:DeleteOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = ["*"]
  }

  # Explicit Deny on the CI roles themselves.
  statement {
    sid    = "DenyCiRoleMutation"
    effect = "Deny"
    actions = [
      "iam:DeleteRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/nica-erp-ci-deploy",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/nica-erp-ci-destroy",
    ]
  }
}

resource "aws_iam_role" "ci_destroy" {
  name                 = "nica-erp-ci-destroy"
  description          = "Assumed by .github/workflows/destroy.yml via OIDC. Scoped to ephemeral-stack destroy + Terraform state R/W. Explicitly denied bootstrap-surface deletion."
  assume_role_policy   = data.aws_iam_policy_document.ci_destroy_trust.json
  max_session_duration = 3600

  tags = {
    Project = "nica-erp"
  }
}

resource "aws_iam_role_policy" "ci_destroy" {
  name   = "nica-erp-ci-destroy-inline"
  role   = aws_iam_role.ci_destroy.id
  policy = data.aws_iam_policy_document.ci_destroy_permissions.json
}
