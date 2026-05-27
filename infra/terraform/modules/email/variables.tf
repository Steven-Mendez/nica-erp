variable "from_address" {
  description = "Operator's email address used as the SES sender identity. AWS will send a verification link to this address; the operator must click it before the first signup."
  type        = string
}

variable "tags" {
  description = "Tags applied to the SES email identity."
  type        = map(string)
  default     = { Project = "nica-erp" }
}
