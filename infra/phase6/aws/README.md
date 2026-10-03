# ARMS AI Phase 6 AWS infrastructure

This directory is a reviewable Terraform/OpenTofu configuration for the
recommended external staging architecture. It contains declarations only.
Phase 6 authorizes local formatting, static validation and credential-free plan
construction where possible. It does not authorize `apply`, backend creation,
credential use, resource creation, DNS mutation, artifact upload, or cost.

## Layout

- the root module supplies pinned compatibility, provider configuration,
  immutable staging metadata and shared validation;
- `modules/` contains narrow provider modules added milestone by milestone;
- secret values never appear in source, variable defaults, plan files or state;
- remote state is deliberately unspecified until an operator approves its
  account, region, encryption, locking and recovery policy.

## Intended local validation

```text
terraform fmt -check -recursive infra/phase6/aws
terraform init -backend=false
terraform validate
terraform plan -refresh=false -input=false
```

The commands above are future operator/developer guidance. `init` can download
providers and therefore needs network approval. A plan can require provider
credentials after resources are introduced. No command in this repository
automatically provisions infrastructure.

## Authority

`EXTERNAL_RESOURCES_CREATED=FALSE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`
