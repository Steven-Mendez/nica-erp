# ALB access logging is deliberately not enabled for the ephemeral demo
# environment — it would require a dedicated S3 bucket with the AWS-account
# log-delivery policy and adds per-request cost for a stack we tear down
# nightly. Re-enable when the stack becomes long-lived (ADR-0023 follow-up).
# nosemgrep: terraform.aws.security.aws-elb-access-logs-not-enabled.aws-elb-access-logs-not-enabled
resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.sg_alb_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false
  drop_invalid_header_fields = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-tg-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    enabled             = true
    path                = "/api/healthz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    protocol            = "HTTP"
  }

  deregistration_delay = 30

  tags = merge(var.tags, { Name = "${var.name_prefix}-tg-api" })
}

# No HTTPS listener: CloudFront terminates TLS at the edge and the ALB
# is reachable only from the CloudFront origin-facing prefix list (see
# `network/main.tf` security group), so plain HTTP between CloudFront
# and the ALB stays inside the AWS backbone (ADR-0020).
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP" # nosemgrep: terraform.aws.security.insecure-load-balancer-tls-version.insecure-load-balancer-tls-version

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
