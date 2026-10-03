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
