output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_ingress_subnet_ids" {
  value = [for subnet in aws_subnet.public_ingress : subnet.id]
}

output "private_workload_subnet_ids" {
  value = [for subnet in aws_subnet.private_workload : subnet.id]
}

output "private_database_subnet_ids" {
  value = [for subnet in aws_subnet.private_database : subnet.id]
}

output "security_group_ids" {
  value = {
    ingress            = aws_security_group.ingress.id
    api                = aws_security_group.api.id
    worker             = aws_security_group.worker.id
    research           = aws_security_group.research.id
    database           = aws_security_group.database.id
    interface_endpoints = aws_security_group.interface_endpoints.id
  }
}

output "dns_tls_placeholders" {
  value = {
    staging_hostname = var.staging_hostname
    certificate_arn  = var.certificate_arn
  }
}
