## 1. Module scaffolding

- [ ] 1.1 Create directories
      `infra/terraform/modules/{network,data,compute,auth,secrets,observability}/`
      and `infra/terraform/envs/demo/`.
- [ ] 1.2 Add `versions.tf` to each module pinning Terraform `>= 1.6`
      and `hashicorp/aws ~> 5.0`. Add `variables.tf` skeletons.
- [ ] 1.3 In each module, declare `default_tags` indirectly via a
      `tags` input variable defaulting to `{ Project = "nica-erp" }`
      and merge it into every resource.

## 2. network module

- [ ] 2.1 Author `network/main.tf`: VPC `10.0.0.0/16`, IGW, NAT
      Gateway in AZ-a, four subnets (`10.0.1.0/24`–`10.0.4.0/24`)
      split public/private × AZ-a/AZ-b.
- [ ] 2.2 Author route tables: public RT routes `0.0.0.0/0` via IGW;
      private RT routes via NAT.
- [ ] 2.3 Add gateway VPC endpoints for S3 and DynamoDB associated
      with the private route tables.
- [ ] 2.4 Define `sg_alb`, `sg_ecs_tasks`, `sg_rds` security groups
      with the ingress chain described in the spec; expose outputs
      `vpc_id`, `public_subnet_ids`, `private_subnet_ids`,
      `sg_alb_id`, `sg_ecs_tasks_id`, `sg_rds_id`.

## 3. data module

- [ ] 3.1 Author `data/main.tf`: `aws_db_subnet_group` covering the
      private subnets; `aws_db_instance` `nica-erp-demo` with the
      flags listed in the spec.
- [ ] 3.2 Generate the master password via
      `resource "random_password" "rds"` and the username
      `nica_erp_demo`.
- [ ] 3.3 Write SSM SecureString parameters
      `/nica-erp/demo/rds/url`, `.../username`, `.../password`. Do
      not emit any of them as Terraform outputs.
- [ ] 3.4 Declare module variables `enable_rds_proxy`,
      `enable_read_replica` (defaults `false`); leave the proxy /
      replica resources unimplemented (out of scope, sprint 01).
- [ ] 3.5 Expose outputs `rds_endpoint`, `rds_port`, `rds_instance_id`.

## 4. auth module

- [ ] 4.1 Author `auth/main.tf`: `aws_cognito_user_pool` `nica-erp-demo`
      with schema attribute `custom:active_tenant`
      (`String`, `Mutable=true`).
- [ ] 4.2 Create the SPA app client `nica-erp-spa`
      (`generate_secret=false`, OAuth code flow, scopes
      `openid email profile`).
- [ ] 4.3 Create `aws_cognito_user_pool_domain` with variable
      `cognito_domain_prefix` default `nica-erp`.
- [ ] 4.4 Expose outputs `user_pool_id`, `user_pool_arn`,
      `user_pool_client_id`, `user_pool_domain`.

## 5. secrets module

- [ ] 5.1 Author `secrets/main.tf`: declare the five concrete SSM
      parameters from RDS + Cognito inputs.
- [ ] 5.2 Declare `/nica-erp/demo/jwt/secret` with `value=""` and
      `lifecycle { ignore_changes = [value] }`.
- [ ] 5.3 Expose outputs `ssm_parameter_arns` (map of name → ARN)
      so the compute module can reference them in its task
      definitions' `secrets` blocks.

## 6. compute module

- [ ] 6.1 Author `compute/cluster.tf`: ECS cluster `nica-erp-demo`,
      Fargate-only, container insights disabled.
- [ ] 6.2 Author `compute/task_definitions.tf`:
      - `nica-erp-api` (CPU 256, mem 512, port 8000, awslogs to
        `/nica-erp/api`, env `APP_ENV=aws`, secrets for
        `DATABASE_URL`, `ALEMBIC_DATABASE_URL`,
        `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`).
      - `nica-erp-migrate` (same definition, container `command`
        override `["alembic","upgrade","head"]`).
- [ ] 6.3 Define IAM execution role (ECR + CloudWatch + SSM read)
      and IAM task role (SSM read on the parameters listed +
      `kms:Decrypt` on `alias/aws/ssm`).
- [ ] 6.4 Author `compute/service.tf`: ECS service `nica-erp-api`,
      desired count 1, attached to the ALB target group, deployment
      strategy rolling 100/200.
- [ ] 6.5 Author `compute/alb.tf`: `aws_lb` `nica-erp-demo-alb`
      (internet-facing, public subnets, `sg_alb`), HTTP `:80`
      listener, target group on port 8000 with health check
      `/api/healthz` (matcher 200, interval 15, timeout 5,
      healthy 2, unhealthy 3).
- [ ] 6.6 Author `compute/autoscaling.tf`:
      `aws_appautoscaling_target` and `aws_appautoscaling_policy`
      with default `min=max=1`, target tracking CPU 50%.
- [ ] 6.7 Expose outputs `cluster_name`, `service_name`,
      `api_task_definition_arn`, `migrate_task_definition_arn`,
      `alb_dns_name`, `alb_arn`, `target_group_arn`,
      `task_subnets` (list of private subnet IDs),
      `task_security_group_id`.

## 7. observability module

- [ ] 7.1 Author `observability/main.tf`: CloudWatch Logs group
      `/nica-erp/api` (`retention_in_days=14`).
- [ ] 7.2 Create SNS topic `nica-erp-alerts` + email subscription
      using variable `alert_email`.
- [ ] 7.3 Author the two CloudWatch alarms (`nica-erp-alb-5xx`,
      `nica-erp-rds-cpu`) per the spec, both wired to the SNS
      topic.
- [ ] 7.4 Expose output `sns_alerts_topic_arn` so later sprint
      domain alarms can subscribe.

## 8. envs/demo composition

- [ ] 8.1 Author `envs/demo/backend.tf` with the S3 backend referenced
      to the bootstrap-created state bucket and lock table.
- [ ] 8.2 Author `envs/demo/main.tf` instantiating the six modules in
      order (network → data → auth → secrets → compute →
      observability) and wiring outputs to inputs.
- [ ] 8.3 Author the CloudFront `/api/*` origin-swap resource using
      `data "aws_cloudfront_distribution"` against the bootstrap
      distribution and the `ignore_changes` set described in the
      design doc.
- [ ] 8.4 Author `envs/demo/variables.tf` (`aws_region`,
      `alert_email`, `image_tag`, `api_min_capacity`,
      `api_max_capacity`, `cognito_domain_prefix`) and
      `envs/demo/terraform.tfvars.example` documenting them.
- [ ] 8.5 Expose `envs/demo` outputs
      `cloudfront_distribution_domain` (re-exposed from the
      bootstrap data source), `alb_dns_name`, `rds_endpoint`,
      `cognito_user_pool_id`, `cognito_user_pool_client_id`.

## 9. Verification

- [ ] 9.1 With `add-terraform-state-backend` applied and an image in
      ECR, run `terraform -chdir=infra/terraform/envs/demo apply`;
      confirm completion in under 25 minutes and the expected
      outputs.
- [ ] 9.2 Curl `https://<dist-id>.cloudfront.net/api/healthz` after a
      5-minute CloudFront propagation wait; confirm HTTP 200, `db:"ok"`,
      and a non-null `alembic_revision`.
- [ ] 9.3 Curl `https://<dist-id>.cloudfront.net/` and confirm the
      SPA `index.html` still serves with HTTP 200 (default behavior
      unaffected).
- [ ] 9.4 Run
      `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=nica-erp`
      and confirm both bootstrap and runtime-stack resources appear.
- [ ] 9.5 Run `terraform plan` again; confirm "No changes" (modulo
      `default_tags` / S3 ETag caveats documented in design).
- [ ] 9.6 Run `terraform destroy -auto-approve`; confirm completion
      in under 15 minutes and that the same Resource Groups query
      now returns only the bootstrap resources.
