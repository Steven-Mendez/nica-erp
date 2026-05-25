## ADDED Requirements

### Requirement: VPC and subnet layout

The `infra/terraform/modules/network/` module SHALL create one VPC
with CIDR `10.0.0.0/16` and tag `Name=nica-erp-demo-vpc`,
`Project=nica-erp`. Within that VPC the module SHALL create, in two
Availability Zones (`us-east-1a` and `us-east-1b` by default), one
public subnet and one private subnet per AZ (four subnets total).
Public subnets SHALL have `map_public_ip_on_launch=true`. The module
SHALL create one Internet Gateway attached to the VPC and one NAT
Gateway in the AZ-a public subnet.

#### Scenario: VPC and subnets are tagged correctly

- **WHEN** `aws ec2 describe-vpcs --filters Name=tag:Project,Values=nica-erp`
  is called after apply
- **THEN** the response SHALL include one VPC with CIDR
  `10.0.0.0/16`, and `aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc-id>`
  SHALL return four subnets evenly split between AZ `us-east-1a`
  and `us-east-1b`

### Requirement: Single NAT Gateway routes private-subnet egress

The module SHALL declare exactly one NAT Gateway and SHALL configure
the private subnets' route tables in both AZs to route
`0.0.0.0/0` through that single NAT Gateway. Public subnets SHALL
route `0.0.0.0/0` through the Internet Gateway.

#### Scenario: Both private subnets share the NAT

- **WHEN** the route tables associated with each private subnet are
  inspected
- **THEN** they SHALL each route `0.0.0.0/0` through the same NAT
  Gateway ID

### Requirement: Gateway VPC endpoints for S3 and DynamoDB

The module SHALL create gateway VPC endpoints
(`com.amazonaws.us-east-1.s3` and
`com.amazonaws.us-east-1.dynamodb`) associated with both private
subnets' route tables. The module SHALL NOT create any Interface
VPC endpoint.

#### Scenario: Endpoints exist and are gateway type

- **WHEN** `aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<vpc-id>`
  is called
- **THEN** the response SHALL list exactly two endpoints, both with
  `VpcEndpointType=Gateway`, with service names ending in `.s3`
  and `.dynamodb`

### Requirement: Security groups enforce CloudFront → ALB → ECS → RDS chain

The module SHALL create three security groups:

- `sg_alb`: inbound TCP `80` SHALL be allowed only from the
  AWS-managed prefix list
  `com.amazonaws.global.cloudfront.origin-facing`; outbound SHALL
  allow all traffic.
- `sg_ecs_tasks`: inbound TCP `8000` SHALL be allowed only from
  `sg_alb`; outbound SHALL allow all traffic.
- `sg_rds`: inbound TCP `5432` SHALL be allowed only from
  `sg_ecs_tasks`; outbound SHALL allow all traffic.

#### Scenario: ALB SG references CloudFront prefix list

- **WHEN** the ingress rules of `sg_alb` are inspected after apply
- **THEN** the only ingress rule SHALL have `IpProtocol=tcp`,
  `FromPort=80`, `ToPort=80`, and `PrefixListIds[0].PrefixListId`
  resolving to the managed
  `com.amazonaws.global.cloudfront.origin-facing` prefix list

#### Scenario: ECS task SG is scoped to ALB SG

- **WHEN** the ingress rules of `sg_ecs_tasks` are inspected
- **THEN** the only ingress rule SHALL have `IpProtocol=tcp`,
  `FromPort=8000`, `ToPort=8000`, and
  `UserIdGroupPairs[0].GroupId` equal to the `sg_alb` ID
