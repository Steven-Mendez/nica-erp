variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = { Project = "nica-erp" }
}

variable "name_prefix" {
  description = "Prefix applied to every Name tag."
  type        = string
  default     = "nica-erp-demo"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs the RDS instance lives in."
  type        = list(string)
}

variable "sg_rds_id" {
  description = "Security group ID controlling RDS ingress."
  type        = string
}

variable "db_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "nica_erp"
}

variable "db_username" {
  description = "Master username for the RDS instance."
  type        = string
  default     = "nica_erp_demo"
}

variable "instance_class" {
  description = "RDS instance class. Demo default is db.t4g.micro."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  description = "Allocated storage in GB. Demo default 20."
  type        = number
  default     = 20
}

variable "postgres_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "17.2"
}

variable "enable_rds_proxy" {
  description = "Toggle for a future RDS Proxy. Sprint 01 leaves this off."
  type        = bool
  default     = false
}

variable "enable_read_replica" {
  description = "Toggle for a future read replica. Sprint 01 leaves this off."
  type        = bool
  default     = false
}
