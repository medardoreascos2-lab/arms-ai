data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${data.aws_region.current.name}.s3"
}

data "aws_region" "current" {}

locals {
  zones = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)
  interface_services = toset([
    "ecr.api",
    "ecr.dkr",
    "logs",
    "secretsmanager",
    "kms",
    "sts",
  ])
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "public_ingress" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-ingress-igw" })
}

resource "aws_subnet" "public_ingress" {
  for_each = { for index, zone in local.zones : zone => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, each.value)
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name     = "${var.name_prefix}-public-${each.key}"
    Boundary = "public-ingress-only"
  })
}

resource "aws_subnet" "private_workload" {
  for_each = { for index, zone in local.zones : zone => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, each.value + 4)
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name     = "${var.name_prefix}-workload-${each.key}"
    Boundary = "private-workload"
  })
}

resource "aws_subnet" "private_database" {
  for_each = { for index, zone in local.zones : zone => index }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, each.value + 8)
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name     = "${var.name_prefix}-database-${each.key}"
    Boundary = "private-database"
  })
}

resource "aws_route_table" "public_ingress" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-public-ingress" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public_ingress.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.public_ingress.id
}

resource "aws_route_table_association" "public_ingress" {
  for_each = aws_subnet.public_ingress

  route_table_id = aws_route_table.public_ingress.id
  subnet_id      = each.value.id
}

resource "aws_route_table" "private_workload" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-private-workload" })
}

resource "aws_route_table_association" "private_workload" {
  for_each = aws_subnet.private_workload

  route_table_id = aws_route_table.private_workload.id
  subnet_id      = each.value.id
}

resource "aws_route_table" "private_database" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-private-database" })
}

resource "aws_route_table_association" "private_database" {
  for_each = aws_subnet.private_database

  route_table_id = aws_route_table.private_database.id
  subnet_id      = each.value.id
}

resource "aws_security_group" "ingress" {
  name_prefix = "${var.name_prefix}-ingress-"
  description = "TLS ingress boundary; sources are explicit and never world-open"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-ingress" })
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  for_each = var.allowed_ingress_cidrs

  security_group_id = aws_security_group.ingress.id
  cidr_ipv4         = each.value
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Operator-approved staging HTTPS source"
}

resource "aws_security_group" "api" {
  name_prefix = "${var.name_prefix}-api-"
  description = "Private API tasks"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-api" })
}

resource "aws_vpc_security_group_ingress_rule" "api_from_ingress" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.ingress.id
  from_port                    = var.api_container_port
  to_port                      = var.api_container_port
  ip_protocol                  = "tcp"
  description                  = "API traffic from the TLS ingress boundary"
}

resource "aws_vpc_security_group_egress_rule" "ingress_to_api" {
  security_group_id            = aws_security_group.ingress.id
  referenced_security_group_id = aws_security_group.api.id
  from_port                    = var.api_container_port
  to_port                      = var.api_container_port
  ip_protocol                  = "tcp"
  description                  = "Ingress boundary to private API tasks"
}

resource "aws_security_group" "worker" {
  name_prefix = "${var.name_prefix}-worker-"
  description = "Operational worker and scheduler tasks"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-worker" })
}

resource "aws_security_group" "research" {
  name_prefix = "${var.name_prefix}-research-"
  description = "Resource-bounded research tasks"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-research" })
}

resource "aws_security_group" "database" {
  name_prefix = "${var.name_prefix}-database-"
  description = "Private PostgreSQL boundary"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-database" })
}

resource "aws_vpc_security_group_ingress_rule" "database" {
  for_each = {
    api      = aws_security_group.api.id
    worker   = aws_security_group.worker.id
    research = aws_security_group.research.id
  }

  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from ${each.key} task boundary"
}

resource "aws_vpc_security_group_egress_rule" "workload_to_database" {
  for_each = {
    api      = aws_security_group.api.id
    worker   = aws_security_group.worker.id
    research = aws_security_group.research.id
  }

  security_group_id            = each.value
  referenced_security_group_id = aws_security_group.database.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "${each.key} tasks to private PostgreSQL"
}

resource "aws_security_group" "interface_endpoints" {
  name_prefix = "${var.name_prefix}-endpoints-"
  description = "Private AWS API endpoints"
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-endpoints" })
}

resource "aws_vpc_security_group_ingress_rule" "endpoints" {
  for_each = {
    api      = aws_security_group.api.id
    worker   = aws_security_group.worker.id
    research = aws_security_group.research.id
  }

  security_group_id            = aws_security_group.interface_endpoints.id
  referenced_security_group_id = each.value
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private AWS APIs from ${each.key} tasks"
}

resource "aws_vpc_security_group_egress_rule" "workload_to_endpoints" {
  for_each = {
    api      = aws_security_group.api.id
    worker   = aws_security_group.worker.id
    research = aws_security_group.research.id
  }

  security_group_id            = each.value
  referenced_security_group_id = aws_security_group.interface_endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "${each.key} tasks to private AWS APIs"
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_services

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [for subnet in aws_subnet.private_workload : subnet.id]
  security_group_ids  = [aws_security_group.interface_endpoints.id]
  tags                = merge(var.tags, { Name = "${var.name_prefix}-${replace(each.value, ".", "-")}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_workload.id]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-s3" })
}

resource "aws_vpc_security_group_egress_rule" "workload_to_s3" {
  for_each = {
    api      = aws_security_group.api.id
    worker   = aws_security_group.worker.id
    research = aws_security_group.research.id
  }

  security_group_id = each.value
  prefix_list_id    = data.aws_prefix_list.s3.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "${each.key} tasks to regional S3 endpoint"
}
