resource "aws_s3_bucket" "tf_state" {
  bucket = local.tf_state_bucket_name

  tags = {
    Project = "nica-erp"
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "tf_state_secure_transport" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.tf_state.arn,
      "${aws_s3_bucket.tf_state.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  policy = data.aws_iam_policy_document.tf_state_secure_transport.json

  depends_on = [aws_s3_bucket_public_access_block.tf_state]
}

# Customer-managed KMS key for the Terraform state-lock table. The
# bootstrap stack is long-lived (it survives `make destroy`), so the
# small recurring KMS cost is appropriate; an AWS-managed key would
# rotate outside our control and the table holds operational metadata.
resource "aws_kms_key" "tf_lock" {
  description             = "CMK for Terraform state-lock DynamoDB table."
  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = {
    Project = "nica-erp"
    Name    = "nica-erp-tf-lock-cmk"
  }
}

resource "aws_kms_alias" "tf_lock" {
  name          = "alias/nica-erp-tf-lock"
  target_key_id = aws_kms_key.tf_lock.id
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = "nica-erp-tf-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.tf_lock.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Project = "nica-erp"
  }
}
