"""R71B static safety checks for the external staging network module."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
NETWORK = ROOT / "infra" / "phase6" / "aws" / "modules" / "network"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(NETWORK.glob("*.tf")))


def test_network_has_two_zone_public_workload_and_database_boundaries():
    text = _text()

    assert 'default = 2' in text
    assert 'var.availability_zone_count == 2' in text
    assert 'resource "aws_subnet" "public_ingress"' in text
    assert 'resource "aws_subnet" "private_workload"' in text
    assert 'resource "aws_subnet" "private_database"' in text
    assert text.count("map_public_ip_on_launch = false") == 3


def test_security_groups_never_define_world_open_ingress_or_general_task_egress():
    text = _text()

    assert 'cidr_ipv4         = "0.0.0.0/0"' not in text
    assert 'cidr_ipv4      = "0.0.0.0/0"' not in text
    assert 'cidr != "0.0.0.0/0"' in text
    assert 'resource "aws_nat_gateway"' not in text
    assert 'resource "aws_vpc_security_group_egress_rule" "workload_to_database"' in text
    assert 'resource "aws_vpc_security_group_egress_rule" "workload_to_endpoints"' in text
    assert 'resource "aws_vpc_security_group_egress_rule" "workload_to_s3"' in text


def test_database_and_aws_api_paths_are_private_and_scoped():
    text = _text()

    assert 'referenced_security_group_id = aws_security_group.database.id' in text
    assert 'from_port                    = 5432' in text
    assert 'vpc_endpoint_type   = "Interface"' in text
    assert 'vpc_endpoint_type = "Gateway"' in text
    assert 'private_dns_enabled = true' in text
    assert re.search(r'publicly_accessible\s*=\s*true', text, re.I) is None


def test_dns_and_tls_are_non_mutating_placeholders():
    text = _text()

    assert 'variable "staging_hostname"' in text
    assert 'variable "certificate_arn"' in text
    assert 'resource "aws_route53_' not in text
    assert 'resource "aws_acm_' not in text
    assert 'resource "aws_lb_listener"' not in text
