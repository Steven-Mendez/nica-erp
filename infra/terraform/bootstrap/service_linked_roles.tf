# Service-linked roles that the AWS services do NOT auto-create when
# first called via the API.
#
# ECS: in particular, `ecs:PutClusterCapacityProviders` and
# `ecs:CreateService` will fail with "Unable to assume the service
# linked role" on a brand-new account unless AWSServiceRoleForECS
# exists. Console interactions create it implicitly; API/SDK calls
# (including terraform) do not. We pin it here so the ephemeral
# stack's apply is reproducible against a fresh account.
#
# ELB, RDS, application-autoscaling DO auto-create their SLRs on first
# API use as long as the caller has iam:CreateServiceLinkedRole (granted
# in oidc.tf). They are intentionally omitted here.

resource "aws_iam_service_linked_role" "ecs" {
  aws_service_name = "ecs.amazonaws.com"
  description      = "Service-linked role for Amazon ECS, pre-created so terraform-driven ECS calls do not need to bootstrap it."
}
