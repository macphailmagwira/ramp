########################################
# Cognito User Pool
########################################

resource "aws_cognito_user_pool" "this" {
  name = var.user_pool_name

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]
  mfa_configuration        = "OFF"

  admin_create_user_config {
    allow_admin_create_user_only = true

    invite_message_template {
      email_subject = "Welcome to StitchSense - Set Up Your Account"

      # SMS message is required by AWS even if not used (min 6 chars)
      sms_message = "Your StitchSense username is {username} and temporary password is {####}"

      email_message = <<-EOT
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
          <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>Welcome to StitchSense</title>
          </head>
          <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f8f9fa;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0; padding: 0;">
              <tr>
                <td align="center" style="padding: 40px 20px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
                    <tr>
                      <td style="padding: 40px 40px 30px 40px; text-align: center; border-bottom: 1px solid #e9ecef;">
                        <h1 style="color: #007bff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 28px; font-weight: 700; margin: 0; letter-spacing: -0.5px;">Welcome to StitchSense!</h1>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding: 40px;">
                        <p style="margin: 0 0 24px 0; font-size: 16px; color: #495057;">You've been invited to join <strong>StitchSense</strong>. We're excited to have you on board!</p>
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 0 0 24px 0;">
                          <p style="margin: 0 0 8px 0; font-size: 14px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Your Account Email</p>
                          <p style="margin: 0; font-size: 16px; color: #007bff; font-weight: 600;">{username}</p>
                        </div>
                        <p style="margin: 0 0 12px 0; font-size: 16px; color: #495057;">Your temporary password is:</p>
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 32px 0;">
                          <tr>
                            <td style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 2px dashed #dee2e6;">
                              <span style="font-size: 24px; font-family: 'Courier New', monospace; color: #212529; font-weight: 700; letter-spacing: 2px;">{####}</span>
                            </td>
                          </tr>
                        </table>
                        <p style="margin: 0 0 20px 0; font-size: 16px; color: #495057;">Click the button below to log in and set up your permanent password:</p>
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 32px 0;">
                          <tr>
                            <td align="center">
                              <a href="${var.app_url}" style="background-color: #007bff; color: #ffffff; padding: 14px 32px; font-weight: 600; text-decoration: none; border-radius: 6px; display: inline-block; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 16px; box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3); transition: background-color 0.2s;">Log In Now</a>
                            </td>
                          </tr>
                        </table>
                        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; border-radius: 6px; margin: 0 0 24px 0;">
                          <p style="margin: 0; font-size: 14px; color: #856404;"><strong>Important:</strong> You'll be prompted to create a new permanent password after your first login.</p>
                        </div>
                        <p style="margin: 0; font-size: 14px; color: #6c757d; line-height: 1.5;">If you have any questions or need assistance, feel free to reach out to our support team.</p>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding: 30px 40px; background-color: #f8f9fa; border-top: 1px solid #e9ecef; border-radius: 0 0 12px 12px;">
                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #6c757d; text-align: center;">
                          If you didn't request this invitation, please ignore this email.
                        </p>
                        <p style="margin: 0; font-size: 14px; color: #adb5bd; text-align: center;">
                          <a href="https://www.stitchsense.ai" style="color: #007bff; text-decoration: none;">www.stitchsense.ai</a>
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </body>
        </html>
      EOT
    }
  }

  lifecycle {
    ignore_changes = [
      schema,
      username_configuration,
      password_policy,
    ]
  }

  tags = var.tags
}

########################################
# Cognito User Pool Client
########################################

resource "aws_cognito_user_pool_client" "app_client" {
  name         = var.app_client_name
  user_pool_id = aws_cognito_user_pool.this.id

  refresh_token_validity = 1
  access_token_validity  = 60
  id_token_validity      = 60

  token_validity_units {
    refresh_token = "days"
    access_token  = "minutes"
    id_token      = "minutes"
  }

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH"
  ]

  generate_secret               = var.generate_secret
  prevent_user_existence_errors = "ENABLED"
}

########################################
# Cognito User Pool Groups
########################################

resource "aws_cognito_user_group" "groups" {
  for_each = { for group in var.user_pool_groups : group.name => group }

  name         = each.value.name
  user_pool_id = aws_cognito_user_pool.this.id
  description  = each.value.description
  precedence   = each.value.precedence
}
