output "foundation" {
  description = "Non-sensitive foundation metadata for plan review."
  value = {
    provider         = "aws"
    region           = var.aws_region
    environment      = var.environment
    name_prefix      = local.name_prefix
    broker_authority = false
    live_authority   = false
    production       = false
  }
}

output "network" {
  description = "Non-secret identifiers for the isolated staging network."
  value = {
    vpc_id                      = module.network.vpc_id
    public_ingress_subnet_ids   = module.network.public_ingress_subnet_ids
    private_workload_subnet_ids = module.network.private_workload_subnet_ids
    private_database_subnet_ids = module.network.private_database_subnet_ids
    security_group_ids          = module.network.security_group_ids
    dns_tls_placeholders        = module.network.dns_tls_placeholders
  }
}

output "database" {
  description = "Private PostgreSQL connection metadata and safety contract."
  value = {
    endpoint    = module.database.endpoint
    port        = module.database.port
    resource_id = module.database.resource_id
    contract    = module.database.contract
  }
}

output "secret_references" {
  description = "Opaque staging secret references and reader policies; no values."
  value = {
    secret_arns        = module.secrets.secret_arns
    reader_policy_arns = module.secrets.reader_policy_arns
    rotation_contract  = module.secrets.rotation_contract
  }
}

output "identity" {
  description = "External OIDC validation contract and isolated service roles."
  value = {
    oidc_contract     = module.identity.oidc_contract
    service_role_arns = module.identity.service_role_arns
  }
}

output "observability" {
  description = "Staging log, metric, alarm and dashboard contract."
  value = {
    log_group_names             = module.observability.log_group_names
    alert_topic_arn             = module.observability.alert_topic_arn
    telemetry_writer_policy_arn = module.observability.telemetry_writer_policy_arn
    contract                    = module.observability.telemetry_contract
  }
}

output "backup" {
  description = "Encrypted off-host backup references and separated access policies."
  value = {
    bucket_arn               = module.backup.bucket_arn
    backup_writer_policy_arn = module.backup.backup_writer_policy_arn
    restore_reader_policy_arn = module.backup.restore_reader_policy_arn
    contract                 = module.backup.backup_contract
  }
}

output "registry" {
  description = "Private immutable OCI registry and separated access policies."
  value = {
    repository_arn      = module.registry.repository_arn
    repository_url      = module.registry.repository_url
    publisher_policy_arn = module.registry.publisher_policy_arn
    puller_policy_arn   = module.registry.puller_policy_arn
    contract            = module.registry.release_contract
  }
}
