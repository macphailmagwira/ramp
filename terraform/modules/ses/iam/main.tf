########################################
# SES IAM SUBMODULE - modules/ses/iam/main.tf
########################################

# IAM Policy Document for sending emails
data "aws_iam_policy_document" "ses_send_email" {
  statement {
    effect = "Allow"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
      "ses:SendTemplatedEmail",
      "ses:SendBulkTemplatedEmail"
    ]
    resources = var.ses_identity_arns

    dynamic "condition" {
      for_each = var.restrict_from_addresses ? [1] : []
      content {
        test     = "StringEquals"
        variable = "ses:FromAddress"
        values   = var.allowed_from_addresses
      }
    }
  }
}

# IAM Policy for SES sending
resource "aws_iam_policy" "ses_send_email" {
  name        = "${var.name_prefix}-ses-send-policy"
  description = "Policy to allow sending emails via SES"
  policy      = data.aws_iam_policy_document.ses_send_email.json

  tags = var.tags
}

# Attach policy to roles
resource "aws_iam_role_policy_attachment" "ses_send_email" {
  for_each   = toset(var.iam_role_names)
  role       = each.value
  policy_arn = aws_iam_policy.ses_send_email.arn
}
