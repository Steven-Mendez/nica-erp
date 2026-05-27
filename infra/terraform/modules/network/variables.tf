variable "tags" {
  description = "Tags applied to every resource. Project tag defaults to nica-erp."
  type        = map(string)
  default     = { Project = "nica-erp" }
}

variable "vpc_cidr" {
  description = "CIDR block for the demo VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "name_prefix" {
  description = "Prefix applied to every Name tag."
  type        = string
  default     = "nica-erp-demo"
}
