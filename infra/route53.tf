# Optionally create a hosted zone in this account (cross-account subdomain delegation).
# Default: use an existing zone via var.hosted_zone_id.
resource "aws_route53_zone" "app" {
  count   = var.create_hosted_zone ? 1 : 0
  name    = var.domain_name
  comment = "Managed by Terraform — Argus for Athena ${var.environment}"
}

locals {
  hosted_zone_id = var.create_hosted_zone ? aws_route53_zone.app[0].zone_id : var.hosted_zone_id
}

resource "aws_route53_record" "app_a" {
  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.app.domain_name
    zone_id                = aws_cloudfront_distribution.app.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "app_aaaa" {
  zone_id = local.hosted_zone_id
  name    = var.domain_name
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.app.domain_name
    zone_id                = aws_cloudfront_distribution.app.hosted_zone_id
    evaluate_target_health = false
  }
}

