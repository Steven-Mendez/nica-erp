output "rds_endpoint" {
  description = "RDS endpoint (hostname only, no port)."
  value       = aws_db_instance.this.address
}

output "rds_port" {
  description = "RDS port (5432)."
  value       = aws_db_instance.this.port
}

output "rds_instance_id" {
  description = "RDS instance identifier."
  value       = aws_db_instance.this.id
}

# Credentials are exposed via this module ONLY for the secrets module to
# consume as SSM SecureString values. They are NOT emitted by the demo
# env (no `output` at the env layer references these). Marked sensitive
# to keep them out of CLI/log output.
output "rds_username" {
  description = "RDS master username (internal — for the secrets module only)."
  value       = aws_db_instance.this.username
  sensitive   = true
}

output "rds_password" {
  description = "RDS master password (internal — for the secrets module only)."
  value       = random_password.rds.result
  sensitive   = true
}

output "rds_database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}
