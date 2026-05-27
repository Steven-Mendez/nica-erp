resource "aws_db_subnet_group" "this" {
  name        = "${var.name_prefix}-db-subnets"
  subnet_ids  = var.private_subnet_ids
  description = "Private subnets for ${var.name_prefix} RDS."

  tags = merge(var.tags, { Name = "${var.name_prefix}-db-subnets" })
}

resource "random_password" "rds" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_instance" "this" {
  identifier             = "${var.name_prefix}-pg"
  engine                 = "postgres"
  engine_version         = var.postgres_version
  instance_class         = var.instance_class
  allocated_storage      = var.allocated_storage_gb
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = var.db_name
  username               = var.db_username
  password               = random_password.rds.result
  port                   = 5432
  vpc_security_group_ids = [var.sg_rds_id]
  db_subnet_group_name   = aws_db_subnet_group.this.name

  # Pre-launch: accept data loss on destroy (ADR-0017).
  skip_final_snapshot          = true
  deletion_protection          = false
  backup_retention_period      = 0
  multi_az                     = false
  publicly_accessible          = false
  performance_insights_enabled = false
  auto_minor_version_upgrade   = true
  apply_immediately            = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-pg" })
}
