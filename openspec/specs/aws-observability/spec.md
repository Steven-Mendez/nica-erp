# aws-observability Specification

## Purpose
TBD - created by archiving change add-aws-runtime-stack. Update Purpose after archive.
## Requirements
### Requirement: CloudWatch Logs group for API container output

The `infra/terraform/modules/observability/` module SHALL create one
`aws_cloudwatch_log_group` named `/nica-erp/api` with
`retention_in_days=14` and tag `Project=nica-erp`. The compute
module's API and migration task definitions SHALL reference this log
group as their `awslogs-group`.

#### Scenario: Log group exists with the expected retention

- **WHEN** `aws logs describe-log-groups --log-group-name-prefix /nica-erp/api`
  is called after apply
- **THEN** the response SHALL list exactly one group with
  `retentionInDays=14`

### Requirement: ALB 5xx alarm

The module SHALL create one `aws_cloudwatch_metric_alarm`
`nica-erp-alb-5xx` watching the metric `HTTPCode_Target_5XX_Count`
on the ALB created by the compute module, with `period=300`,
`evaluation_periods=1`, `statistic="Sum"`, `comparison_operator="GreaterThanThreshold"`,
`threshold=<dynamic>` corresponding to "more than 1% of total
requests in any 5-minute window" (implementation MAY use a metric
math expression dividing 5xx by total requests).
`treat_missing_data="notBreaching"`. The alarm SHALL emit
notifications to the SNS topic `nica-erp-alerts`.

#### Scenario: Alarm exists and targets the SNS topic

- **WHEN** `aws cloudwatch describe-alarms --alarm-names nica-erp-alb-5xx`
  is called after apply
- **THEN** the response SHALL include `AlarmActions` containing the
  ARN of the `nica-erp-alerts` SNS topic

### Requirement: RDS CPU alarm

The module SHALL create one `aws_cloudwatch_metric_alarm`
`nica-erp-rds-cpu` watching the metric `CPUUtilization` on the RDS
instance from the data module, with `period=300`,
`evaluation_periods=2`, `statistic="Average"`,
`comparison_operator="GreaterThanOrEqualToThreshold"`,
`threshold=80`, `treat_missing_data="notBreaching"`. The alarm
SHALL emit notifications to the SNS topic `nica-erp-alerts`.

#### Scenario: Alarm fires at the documented threshold

- **WHEN** the alarm is inspected after apply
- **THEN** `Threshold` SHALL equal `80`, `EvaluationPeriods` SHALL
  equal `2`, and `Period` SHALL equal `300`

### Requirement: SNS topic `nica-erp-alerts` with email subscription

The module SHALL create one `aws_sns_topic` named
`nica-erp-alerts` and one `aws_sns_topic_subscription` of
`protocol="email"` whose `endpoint` is the variable `alert_email`
(required, no default). The topic SHALL carry the tag
`Project=nica-erp`.

#### Scenario: Email subscription is requested

- **WHEN** the module is applied with `alert_email="ops@example.com"`
- **THEN** an email subscription SHALL exist on the
  `nica-erp-alerts` topic with endpoint `ops@example.com`, even if
  the subscription is in `PendingConfirmation` state until the
  recipient confirms

