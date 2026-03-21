########################################
# SES MODULE - modules/ses/main.tf
########################################

# SES Email Identity - Domain verification
resource "aws_ses_domain_identity" "main" {
  domain = var.domain
}

# SES Domain DKIM - Email authentication
resource "aws_ses_domain_dkim" "main" {
  domain = aws_ses_domain_identity.main.domain
}

# Route53 Records for Domain Verification
resource "aws_route53_record" "ses_verification" {
  count   = var.create_route53_records ? 1 : 0
  zone_id = var.route53_zone_id
  name    = "_amazonses.${aws_ses_domain_identity.main.domain}"
  type    = "TXT"
  ttl     = 600
  records = [aws_ses_domain_identity.main.verification_token]
}

# Route53 Records for DKIM (email authentication)
resource "aws_route53_record" "ses_dkim" {
  count   = var.create_route53_records ? 3 : 0
  zone_id = var.route53_zone_id
  name    = "${element(aws_ses_domain_dkim.main.dkim_tokens, count.index)}._domainkey.${aws_ses_domain_identity.main.domain}"
  type    = "CNAME"
  ttl     = 600
  records = ["${element(aws_ses_domain_dkim.main.dkim_tokens, count.index)}.dkim.amazonses.com"]
}

# SES Configuration Set for tracking
resource "aws_ses_configuration_set" "main" {
  name = var.configuration_set_name

  delivery_options {
    tls_policy = var.tls_policy
  }

  reputation_metrics_enabled = var.enable_reputation_metrics
  sending_enabled           = var.sending_enabled
}

# CloudWatch for SES metrics
resource "aws_ses_event_destination" "cloudwatch" {
  count                  = var.enable_cloudwatch_events ? 1 : 0
  name                   = "cloudwatch-destination"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true
  matching_types         = var.cloudwatch_event_types

  cloudwatch_destination {
    default_value  = "default"
    dimension_name = "ses:configuration-set"
    value_source   = "messageTag"
  }
}

# SNS for bounce/complaint notifications
resource "aws_ses_event_destination" "sns" {
  count                  = var.enable_sns_events ? 1 : 0
  name                   = "sns-destination"
  configuration_set_name = aws_ses_configuration_set.main.name
  enabled                = true
  matching_types         = var.sns_event_types

  sns_destination {
    topic_arn = var.sns_topic_arn
  }
}

# Email templates
resource "aws_ses_template" "templates" {
  for_each = var.email_templates

  name    = each.key
  subject = each.value.subject
  html    = each.value.html
  text    = each.value.text
}

# Verified email addresses (for testing or specific senders)
resource "aws_ses_email_identity" "emails" {
  for_each = toset(var.verified_emails)
  email    = each.value
}

# Receipt rule set (optional - for receiving emails)
resource "aws_ses_receipt_rule_set" "main" {
  count          = var.enable_email_receiving ? 1 : 0
  rule_set_name  = var.receipt_rule_set_name
}

resource "aws_ses_active_receipt_rule_set" "main" {
  count          = var.enable_email_receiving ? 1 : 0
  rule_set_name  = aws_ses_receipt_rule_set.main[0].rule_set_name
}
