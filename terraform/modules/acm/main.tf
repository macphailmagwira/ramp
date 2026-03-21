resource "aws_acm_certificate" "cert" {
  for_each = var.certificates

  domain_name               = each.value.domain_name
  validation_method         = lookup(each.value, "validation_method", "DNS")
  subject_alternative_names = lookup(each.value, "subject_alternative_names", [])

  tags = {
    Name        = "stitchsense-cert-${each.key}"
    Environment = "production"
    Project     = "StitchSense"
    Owner       = "DevOps"
  }

  lifecycle {
    create_before_destroy = true
  }
}



# Flatten DVOs to be able to create Route53 records
locals {
  dvo_records = var.route53_zone_id == "" ? {} : {
    for pair in flatten([
      for cert_key, cert in aws_acm_certificate.cert : [
        for dvo in cert.domain_validation_options : {
          key   = "${cert_key}:${dvo.domain_name}"
          zone  = var.route53_zone_id
          name  = dvo.resource_record_name
          type  = dvo.resource_record_type
          value = dvo.resource_record_value
        }
      ]
    ]) : pair.key => pair
  }
}

resource "aws_route53_record" "validation_records" {
  for_each = local.dvo_records

  zone_id = each.value.zone
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.value]

  allow_overwrite = true


}



resource "aws_acm_certificate_validation" "validation" {
  for_each = aws_acm_certificate.cert

  certificate_arn = each.value.arn
  validation_record_fqdns = [
    for dvo in each.value.domain_validation_options :
    aws_route53_record.validation_records["${each.key}:${dvo.domain_name}"].fqdn
  ]
}