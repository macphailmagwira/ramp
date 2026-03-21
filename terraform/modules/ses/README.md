# SES Terraform Module

Modular, reusable Terraform configuration for AWS Simple Email Service (SES).

## Features

✅ **Domain Verification** - Automatic DNS records for domain verification  
✅ **DKIM Authentication** - Email authentication to prevent spoofing  
✅ **Configuration Sets** - Track email metrics and events  
✅ **CloudWatch Integration** - Monitor sends, bounces, complaints  
✅ **SNS Notifications** - Get alerted on bounces and complaints  
✅ **Email Templates** - Manage templated emails  
✅ **IAM Policies** - Secure permissions for sending emails  
✅ **Multi-Environment** - Easy to deploy to staging/production  

## Module Structure

```
modules/ses/
├── main.tf                    # Main SES resources
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── iam/
│   ├── main.tf               # IAM policies for SES sending
│   ├── variables.tf
│   └── outputs.tf
└── templates/
    └── user_invite.tftpl     # Email templates
```

## Usage

### Basic Example

```hcl
module "ses" {
  source = "../../modules/ses"

  domain                  = "stitchsense.ai"
  configuration_set_name  = "stitchsense-staging-emails"
  environment             = "staging"

  create_route53_records  = true
  route53_zone_id         = "Z0695564227B1XIS89WTI"

  email_templates = {
    user-invite-template = {
      subject = "You're invited!"
      html    = file("./templates/user_invite.html")
      text    = file("./templates/user_invite.txt")
    }
  }

  verified_emails = ["noreply@stitchsense.ai"]
}
```

### With IAM Permissions

```hcl
module "ses_iam" {
  source = "../../modules/ses/iam"

  name_prefix         = "stitchsense-staging"
  ses_identity_arns   = [module.ses.domain_identity_arn]
  iam_role_names      = ["stitchsense-staging-ec2-role"]

  restrict_from_addresses = true
  allowed_from_addresses  = ["noreply@stitchsense.ai"]
}
```

### Production Example with SNS Alerts

```hcl
module "ses_production" {
  source = "../../modules/ses"

  domain                  = "stitchsense.ai"
  configuration_set_name  = "stitchsense-production-emails"

  enable_sns_events       = true
  sns_topic_arn          = aws_sns_topic.ses_alerts.arn
  sns_event_types        = ["bounce", "complaint"]

  # ... other settings
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| domain | Domain name to verify | string | - | yes |
| configuration_set_name | Name of configuration set | string | - | yes |
| environment | Environment name | string | "staging" | no |
| create_route53_records | Create DNS records | bool | true | no |
| route53_zone_id | Route53 zone ID | string | "" | no |
| enable_cloudwatch_events | Enable CloudWatch monitoring | bool | true | no |
| enable_sns_events | Enable SNS notifications | bool | false | no |
| email_templates | Map of email templates | map(object) | {} | no |
| verified_emails | List of verified emails | list(string) | [] | no |

See `variables.tf` for complete list.

## Outputs

| Name | Description |
|------|-------------|
| domain_identity_arn | ARN of SES domain identity |
| configuration_set_name | Configuration set name |
| dkim_tokens | DKIM tokens (sensitive) |
| verified_email_identities | Map of verified emails |

See `outputs.tf` for complete list.

## Email Templates

Email templates support variable substitution using `{{variable}}` syntax:

```html
<p>Hi {{first_name}},</p>
<p>You've been invited to join {{tenant_name}}.</p>
<a href="{{activation_link}}">Activate Account</a>
```

### Available Variables (User Invite Template)

- `{{first_name}}` - User's first name
- `{{tenant_name}}` - Organization name
- `{{role}}` - User's role
- `{{activation_link}}` - Account activation URL

## Setup Steps

1. **Apply Terraform**
   ```bash
   terraform apply
   ```

2. **Wait for Domain Verification** (24-72 hours)
   - DNS records are created automatically
   - Check AWS SES Console for verification status

3. **Request Production Access**
   - Go to AWS SES Console → Account dashboard
   - Click "Request production access"
   - Fill out form (usually approved in 24 hours)

4. **Test Email Sending**
   ```python
   from src.services.email_service import get_email_service
   
   service = get_email_service()
   service.send_user_invite_email(
       to_email="test@example.com",
       first_name="Test",
       tenant_name="Test Org",
       role="Manager",
       activation_link="https://app.example.com/activate/123"
   )
   ```

## Monitoring

### CloudWatch Metrics

View metrics in CloudWatch:
- Go to CloudWatch → Metrics → SES
- View sends, bounces, complaints, delivery rates

### SNS Alerts

If `enable_sns_events = true`:
- Bounces and complaints trigger SNS notifications
- Subscribe email/SMS to SNS topic for alerts

## Security Best Practices

✅ **Use DKIM** - Enabled by default for email authentication  
✅ **Require TLS** - Encrypted email transmission  
✅ **Restrict from addresses** - Limit which addresses can send  
✅ **Monitor bounces** - Set up SNS alerts for high bounce rates  
✅ **Use IAM least privilege** - Only grant necessary SES permissions  

## Cost

- **Free Tier**: 62,000 emails/month (if sending from EC2)
- **After Free Tier**: $0.10 per 1,000 emails
- **Example**: 100,000 emails/month = ~$3.80/month

## Troubleshooting

### Domain not verifying?
- Check Route53 records were created
- Wait 24-72 hours for DNS propagation
- Run: `dig TXT _amazonses.stitchsense.ai`

### Emails going to spam?
- Ensure DKIM is configured (automatic)
- Add SPF record: `v=spf1 include:amazonses.com ~all`
- Add DMARC record: `_dmarc.stitchsense.ai TXT "v=DMARC1; p=quarantine"`
- Start with low volume, ramp up gradually

### Can't send to all emails?
- Still in sandbox mode
- Request production access in AWS Console
- SES → Account dashboard → Request production access

## Examples

See:
- `staging_ses_usage.tf` - Staging environment example
- `production_ses_example.tf` - Production with SNS alerts

## License

MIT
