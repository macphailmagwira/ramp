// modules/route53/main.tf
resource "aws_route53_zone" "this" {
  name = var.domain_name
}

resource "aws_route53_record" "root_a" {
  zone_id = var.hosted_zone_id
  name    = "${var.domain_name}."
  type    = "A"
  ttl     = 600
  records = ["75.2.70.75"]
}

resource "aws_route53_record" "root_mx" {
  zone_id = var.hosted_zone_id
  name    = "${var.domain_name}."
  type    = "MX"
  ttl     = 3600
  records = [
    "1 aspmx.l.google.com.",
    "1 smtp.google.com.",
    "10 alt3.aspmx.l.google.com.",
    "10 alt4.aspmx.l.google.com.",
    "5 alt1.aspmx.l.google.com.",
    "5 alt2.aspmx.l.google.com.",
  ]
}

resource "aws_route53_record" "root_ns" {
  zone_id = var.hosted_zone_id
  name    = "${var.domain_name}."
  type    = "NS"
  ttl     = 172800
  records = [
    "ns-1954.awsdns-52.co.uk.",
    "ns-962.awsdns-56.net.",
    "ns-35.awsdns-04.com.",
    "ns-1510.awsdns-60.org.",
  ]
}

resource "aws_route53_record" "root_soa" {
  zone_id = var.hosted_zone_id
  name    = "${var.domain_name}."
  type    = "SOA"
  ttl     = 900
  records = [
    "ns-1954.awsdns-52.co.uk. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400",
  ]
}

resource "aws_route53_record" "root_txt_spf" {
  zone_id = var.hosted_zone_id
  name    = "${var.domain_name}."
  type    = "TXT"
  ttl     = 3600
  records = [
    "v=spf1 include:_spf.google.com ~all",
  ]
}

resource "aws_route53_record" "acm_validation" {
  zone_id = var.hosted_zone_id
  name    = "_b1cb1ee414d4b7c8606c8cd3f491bfb0.${var.domain_name}."
  type    = "CNAME"
  ttl     = 300
  records = [
    "_9d4629424ec3c30b551b1820cd0905c1.xlfgrmvvlj.acm-validations.aws.",
  ]
}

resource "aws_route53_record" "dmarc" {
  zone_id = var.hosted_zone_id
  name    = "_dmarc.${var.domain_name}."
  type    = "TXT"
  ttl     = 3600
  records = [
    "v=DMARC1; p=reject; adkim=r; aspf=r; rua=mailto:alexis@stitchsense.ai,mailto:dmarc_rua@onsecureserver.net",
  ]
}

resource "aws_route53_record" "domainconnect" {
  zone_id = var.hosted_zone_id
  name    = "_domainconnect.${var.domain_name}."
  type    = "CNAME"
  ttl     = 3600
  records = [
    "_domainconnect.gd.domaincontrol.com.",
  ]
}

resource "aws_route53_record" "google_dkim" {
  zone_id = var.hosted_zone_id
  name    = "google._domainkey.${var.domain_name}."
  type    = "TXT"
  ttl     = 300
  records = [
    "v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAv/nYOvjCCnUaHbWLNjNOuDdjCXVOo+1+",
    "KNgS1lOBDQrLtHDpPR1kpz0TY8+CKQCOBjTSjbtwqi3JIsFItORo7Iao4UlGvExZAb1A44YmpRXEj69DOsm8/TpC6u19HHr+GjuCzPGglGyoyINinqjKTtQbwK6qJw/2Rb6tsgDe+qBae/1VoFxku1Pgm5BG9G8ACTaNLF4AEsqVc/pu3se1WVmQixAd6ZuAtotJgKhkDEdU+",
    "fx3FlCu7mbxpXhAFxKOgdpaZTF8xDI2gY/WJwR2cc3tFMkVVMsxTfZ+GwV+Bh9u/+b99t/rk1XhlKZUrOLJNyrxiUe/sfA6tDI4wIDAQAB",
  ]
}

resource "aws_route53_record" "api_dev" {
  zone_id = var.hosted_zone_id
  name    = "api-dev.${var.domain_name}."
  type    = "A"

  alias {
    name                   = "d16dvibi2yzucm.cloudfront.net."
    zone_id                = "Z2FDTNDATAQYW2"
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api_staging" {
  zone_id = var.hosted_zone_id
  name    = "api-staging.${var.domain_name}."
  type    = "A"

  alias {
    name                   = "dujkauq6tc8ne.cloudfront.net."
    zone_id                = "Z2FDTNDATAQYW2"
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "api" {
  zone_id = var.hosted_zone_id
  name    = "api.${var.domain_name}."
  type    = "A"
  ttl     = 300
  records = ["52.74.170.173"]
}

resource "aws_route53_record" "app_dev" {
  zone_id = var.hosted_zone_id
  name    = "app-dev.${var.domain_name}."
  type    = "A"

  alias {
    name                   = "d35en2zhxpyboy.cloudfront.net."
    zone_id                = "Z2FDTNDATAQYW2"
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "app_staging" {
  zone_id = var.hosted_zone_id
  name    = "app-staging.${var.domain_name}."
  type    = "A"

  alias {
    name                   = "daf3w0op5hsc9.cloudfront.net."
    zone_id                = "Z2FDTNDATAQYW2"
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "app" {
  zone_id = var.hosted_zone_id
  name    = "app.${var.domain_name}."
  type    = "A"
  ttl     = 300
  records = ["52.74.170.173"]
}

resource "aws_route53_record" "display" {
  zone_id = var.hosted_zone_id
  name    = "display.${var.domain_name}."
  type    = "A"
  ttl     = 300
  records = ["52.74.170.173"]
}

resource "aws_route53_record" "www" {
  zone_id = var.hosted_zone_id
  name    = "www.${var.domain_name}."
  type    = "CNAME"
  ttl     = 3600
  records = ["${var.domain_name}."]
}
