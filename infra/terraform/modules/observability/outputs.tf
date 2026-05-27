output "log_group_name" {
  description = "CloudWatch Logs group name for the API."
  value       = aws_cloudwatch_log_group.api.name
}

output "log_group_arn" {
  description = "CloudWatch Logs group ARN."
  value       = aws_cloudwatch_log_group.api.arn
}

output "sns_alerts_topic_arn" {
  description = "SNS topic ARN that domain alarms in later sprints subscribe to."
  value       = aws_sns_topic.alerts.arn
}
