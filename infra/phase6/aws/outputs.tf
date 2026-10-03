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
