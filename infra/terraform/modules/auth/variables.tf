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

variable "cognito_domain_prefix" {
  description = "Cognito hosted-domain prefix; final domain is <prefix>.auth.<region>.amazoncognito.com."
  type        = string
  default     = "nica-erp"
}
