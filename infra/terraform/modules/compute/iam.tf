# ECS task IAM:
#   - Execution role: the role ECS itself uses to pull the image,
#     write logs, and resolve SSM `secrets` into the container env.
#   - Task role: the role the running container assumes for its own
#     AWS calls (currently none — sprint 01 does not call AWS from
#     inside the API). Declared so later sprints (sales -> S3 files,
#     outbox -> SQS) can attach policies without recreating it.

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, { Name = "${var.name_prefix}-ecs-execution" })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Inline policy: read the SSM parameters consumed via the `secrets`
# block of each task definition, and decrypt via the AWS-managed SSM
# KMS key.
data "aws_iam_policy_document" "execution_ssm_read" {
  statement {
    sid       = "SsmReadParams"
    effect    = "Allow"
    actions   = ["ssm:GetParameters", "ssm:GetParameter"]
    resources = values(var.ssm_parameter_arns)
  }

  statement {
    sid       = "KmsDecryptForSsm"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "execution_ssm_read" {
  name   = "${var.name_prefix}-ecs-execution-ssm-read"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_ssm_read.json
}

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, { Name = "${var.name_prefix}-ecs-task" })
}

# ---- Task role: cognito-idp allow-list -------------------------------------
#
# The API forwards SPA credentials to Cognito (the SPA does NOT call
# Cognito directly — see ADR-0020). The allow-list below is the exact
# set of cognito-idp actions the identity context calls. Destructive
# actions (AdminDeleteUser, DeleteUserPool*, AdminSetUserPassword) are
# intentionally omitted; the API does not perform them.

data "aws_iam_policy_document" "task_cognito_idp" {
  statement {
    sid    = "CognitoIdpAllowList"
    effect = "Allow"
    actions = [
      "cognito-idp:SignUp",
      "cognito-idp:ConfirmSignUp",
      "cognito-idp:ResendConfirmationCode",
      "cognito-idp:InitiateAuth",
      "cognito-idp:GlobalSignOut",
      "cognito-idp:ForgotPassword",
      "cognito-idp:ConfirmForgotPassword",
      "cognito-idp:ChangePassword",
      "cognito-idp:AdminUpdateUserAttributes",
      "cognito-idp:AdminGetUser",
    ]
    resources = [var.cognito_user_pool_arn]
  }
}

resource "aws_iam_role_policy" "task_cognito_idp" {
  name   = "${var.name_prefix}-ecs-task-cognito-idp"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_cognito_idp.json
}

# ---- Task role: SES send (sandbox) -----------------------------------------
#
# SESv1 SendEmail / SendRawEmail does not support resource-level ARN
# granularity in the MVP region. Scoped to `*`; the verified-sender
# rules in SES (sandbox + single email-identity) provide the actual
# enforcement.

data "aws_iam_policy_document" "task_ses_send" {
  statement {
    sid    = "SesSend"
    effect = "Allow"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "task_ses_send" {
  name   = "${var.name_prefix}-ecs-task-ses-send"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_ses_send.json
}
