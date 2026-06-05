## ADDED Requirements

### Requirement: ECR repository `nica-erp` accepts API container images

The bootstrap Terraform root SHALL create an ECR repository named
`nica-erp` with `image_tag_mutability = "IMMUTABLE"` and
`image_scanning_configuration.scan_on_push = true`. The repository
SHALL carry the tag `Project=nica-erp`.

#### Scenario: Repository exists with immutable tags

- **WHEN** `aws ecr describe-repositories --repository-names nica-erp`
  is called after bootstrap
- **THEN** the response SHALL show `imageTagMutability=IMMUTABLE` and
  `imageScanningConfiguration.scanOnPush=true`

### Requirement: ECR lifecycle policy keeps only the last 5 images

The `nica-erp` repository SHALL carry a lifecycle policy that expires
any image once more than 5 images of any tag status exist, ordered by
`imagePushedAt` descending. The policy SHALL apply to **any** tagged
or untagged image (rule selection `tagStatus=any`).

#### Scenario: Lifecycle policy is attached

- **WHEN** `aws ecr get-lifecycle-policy --repository-name nica-erp`
  is called after bootstrap
- **THEN** the response SHALL include a rule selecting
  `tagStatus=any` with `countType=imageCountMoreThan` and
  `countNumber=5`

#### Scenario: Older images expire automatically

- **WHEN** a sixth image is pushed to the repository
- **THEN** within one ECR lifecycle evaluation cycle, the oldest image
  in the repository SHALL transition to `expired`
